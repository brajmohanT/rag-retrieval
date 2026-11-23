"""BM25 keyword retrieval over page Markdown.

score(page, query) = sum over query terms t of
    idf(t) * tf * (k1 + 1) / (tf + k1 * (1 - b + b * page_length / average_length))
idf(t) = ln(1 + (N - df + 0.5) / (df + 0.5))        (Lucene's BM25 variant)

tf: times t occurs in the page; df: pages containing t; N: pages in the corpus.
k1 limits how much repeated terms help; b sets how much long pages are penalized.
Each distinct query term counts once.
"""

from collections import Counter, defaultdict
from math import log
import re

import snowballstemmer

# Numbers keep decimal and thousands separators ("4.5", "1,200"); words are letter runs.
TOKEN = re.compile(r"\d+(?:[.,]\d+)*|[^\W\d_]+")
STOPWORDS = frozenset("""
a about above after again against all am an and any are as at be because been before being below between
both but by can could did do does doing down during each few for from further had has have having he her
here hers herself him himself his how i if in into is it its itself just me more most my myself no nor not
now of off on once only or other our ours ourselves out over own same she should so some such than that the
their theirs them themselves then there these they this those through to too under until up very was we were
what when where which while who whom why will with would you your yours yourself yourselves
""".split())
STEMMER = snowballstemmer.stemmer("english")


def tokenize(text):
    words = [w for w in TOKEN.findall(text.lower()) if w not in STOPWORDS]
    return STEMMER.stemWords(words)


class BM25:
    def __init__(self, pages, k1=1.2, b=0.75):
        """pages: page_id -> text."""
        self.k1, self.b = k1, b
        self.postings = defaultdict(dict)  # term -> {page_id: tf}
        self.length = {}
        for page_id, text in pages.items():
            tokens = tokenize(text)
            self.length[page_id] = len(tokens)
            for term, tf in Counter(tokens).items():
                self.postings[term][page_id] = tf
        self.average_length = sum(self.length.values()) / len(self.length)
        n = len(self.length)
        self.idf = {term: log(1 + (n - len(docs) + 0.5) / (len(docs) + 0.5)) for term, docs in self.postings.items()}

    def term_score(self, term, page_id):
        tf = self.postings[term].get(page_id, 0)
        norm = 1 - self.b + self.b * self.length[page_id] / self.average_length
        return self.idf[term] * tf * (self.k1 + 1) / (tf + self.k1 * norm)

    def search(self, query, k=100):
        """Top-k (page_id, score), best first; pages sharing no query term are not returned."""
        scores = defaultdict(float)
        for term in set(tokenize(query)):
            for page_id in self.postings.get(term, ()):
                scores[page_id] += self.term_score(term, page_id)
        return sorted(scores.items(), key=lambda item: (-item[1], item[0]))[:k]

    def explain(self, query, page_id):
        """Each matching query term's contribution to the page score, largest first."""
        terms = {t for t in tokenize(query) if page_id in self.postings.get(t, ())}
        return sorted(((t, self.term_score(t, page_id)) for t in terms), key=lambda item: -item[1])
