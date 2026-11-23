"""Answer a question from retrieved pages only, citing them, and grade the answer.

The answering model sees the question and the retrieved pages, each labelled
[p<page_id>], as extracted text, page images, or both (`mode`). It never sees reference answers or relevance
labels; those are used only by `grade`, a separate call that compares the
answer with the dataset's reference answer.
"""

import base64
import re

from evidence_atlas.providers import openrouter

MODEL = openrouter.DEEPSEEK_FLASH
PAGE_CHARS = 6000  # per page; longer pages are cut so five pages fit comfortably
ABSTAIN = "Not enough evidence"
CITATION = re.compile(r"\[p(\d+)\]")
VERDICT = re.compile(r"\b(CORRECT|PARTIAL|INCORRECT)\b")

ANSWER_RULES = f"""You answer questions about EU labour-market reports using ONLY the pages provided.
Rules:
- Cite the page for every claim as [p<number>], e.g. [p485]. Cite only pages you were given.
- Be concise: 1 to 4 sentences, keeping exact figures, years, and countries from the pages.
- If the pages do not contain the answer, reply exactly: "{ABSTAIN}." and nothing else."""

GRADE_RULES = """You grade an answer against a reference answer to the same question.
Reply with exactly one word:
CORRECT   - the answer states the reference's key facts (figures, entities, direction) without contradicting it
PARTIAL   - some key facts are right, but important ones are missing or wrong
INCORRECT - the key facts are wrong, missing, or contradict the reference"""


def chat(messages, max_tokens):
    """DeepSeek reply text and cost. A reasoning model can spend its whole output budget on hidden
    reasoning and return nothing; then retry once with double the budget."""
    reply = openrouter.chat(messages, MODEL, max_tokens=max_tokens)
    cost = reply["usage"].get("cost") or 0
    if not reply["text"].strip():
        reply = openrouter.chat(messages, MODEL, max_tokens=2 * max_tokens)
        cost += reply["usage"].get("cost") or 0
    return reply["text"].strip(), cost


def page_block(page_id, data):
    page = data.pages[page_id]
    text = page.markdown.strip() or "[This page has no extracted text.]"
    cut = " [...]" if len(text) > PAGE_CHARS else ""
    return f"[p{page_id}] {page.doc_id}, PDF page {page.page_number + 1}\n{text[:PAGE_CHARS]}{cut}"


def page_parts(page_id, data, mode, images):
    """Message parts for one page: its label, then its text and/or its image."""
    if mode == "text":
        return [{"type": "text", "text": page_block(page_id, data)}]
    page = data.pages[page_id]
    label = f"[p{page_id}] {page.doc_id}, PDF page {page.page_number + 1} (page image follows)"
    image = {"type": "image_url",
             "image_url": {"url": "data:image/webp;base64," + base64.b64encode(images[page_id]).decode()}}
    if mode == "image":
        return [{"type": "text", "text": label}, image]
    return [{"type": "text", "text": page_block(page_id, data)}, image]


def answer(question, page_ids, data, mode="text", images=None, max_tokens=2000):
    """{"text", "cited", "invalid_citations", "abstained", "cost_usd"} for one question and its retrieved pages.

    mode: "text" (extracted text), "image" (page images only), or "both". images: page_id -> WebP bytes.
    """
    parts = [{"type": "text", "text": "Pages:"}]
    for page_id in page_ids:
        parts += page_parts(page_id, data, mode, images)
    parts.append({"type": "text", "text": f"Question: {question}"})
    content = "\n\n".join(p["text"] for p in parts) if mode == "text" else parts
    messages = [{"role": "system", "content": ANSWER_RULES}, {"role": "user", "content": content}]
    text, cost = chat(messages, max_tokens)
    cited = sorted({int(p) for p in CITATION.findall(text)})
    return {"text": text, "cited": cited, "invalid_citations": [p for p in cited if p not in page_ids],
            "abstained": text.startswith(ABSTAIN), "cost_usd": cost}


def grade(question, reference, text, max_tokens=1000):
    """CORRECT, PARTIAL, or INCORRECT, plus the grading call's cost."""
    messages = [{"role": "system", "content": GRADE_RULES},
                {"role": "user",
                 "content": f"Question: {question}\n\nReference answer: {reference}\n\nAnswer to grade: {text}"}]
    text, cost = chat(messages, max_tokens)
    match = VERDICT.search(text.upper())
    return (match.group(1) if match else "UNPARSED"), cost
