import { useEffect, useState } from 'react'
import { api, pct, type Config, type Meta, type QuestionDetail, type ShowcaseItem } from './api'
import { Comparison } from './Comparison'
import { Scoreboard } from './Scoreboard'
import { BEST, COLQWEN, HYBRID, KEYWORD, PRESETS } from './words'

type Props = { configs: Map<string, Config>; meta: Meta; showcase: ShowcaseItem[] }

// The whole story on one page: results, pipeline, worked examples, method.
export function Overview({ configs, meta, showcase }: Props) {
  const [example, setExample] = useState(0)
  const [detail, setDetail] = useState<QuestionDetail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const c = (id: string) => configs.get(id)!
  const ndcg = (id: string) => c(id).heldout['ndcg@10'].mean.toFixed(2)
  const tables = (id: string) => c(id).heldout_by_content_type.Table['ndcg@10'].toFixed(2)
  const item = showcase[example]

  useEffect(() => {
    api.question(item.query_id, item.lanes).then(setDetail, (e) => setError(String(e)))
  }, [item])

  return (
    <article className="overview">
      <header className="hero">
        <h1>
          Which retriever
          <br />
          finds the page?
        </h1>
        <p className="hero-sub">
          BM25, dense text, visual and hybrid retrieval on {meta.pages.toLocaleString()} report pages and {meta.questions}{' '}
          queries from{' '}
          <a href="https://huggingface.co/datasets/vidore/vidore_v3_hr" target="_blank" rel="noreferrer">
            ViDoRe V3 HR
          </a>
          .
        </p>
        <ul className="facts">
          <li>
            <b>Visual beats text.</b>
            <span>
              nDCG@10 {ndcg(COLQWEN)} vs {ndcg(KEYWORD)}; tables {tables(COLQWEN)} vs {tables(KEYWORD)}
            </span>
          </li>
          <li>
            <b>Reranking adds most.</b>
            <span>
              RRF(all 4) {ndcg(HYBRID)} → {ndcg(BEST)}
            </span>
          </li>
          <li>
            <b>Better retrieval, better answers.</b>
            <span>
              {pct(c(KEYWORD).answers!.correct)} → {pct(c(BEST).answers!.correct)} correct
            </span>
          </li>
        </ul>
      </header>

      <section aria-labelledby="results">
        <h2 id="results" className="section-title">
          Results · 211 held-out queries
        </h2>
        <Scoreboard lanes={PRESETS.map(c)} />
      </section>

      <section aria-labelledby="pipeline">
        <h2 id="pipeline" className="section-title">
          Pipeline
        </h2>
        <ol className="pipeline">
          <li>
            <b>Index</b>
            <span>BM25 · Qwen3-Emb-8B on text</span>
            <span>Voyage-mm-3.5 · ColQwen3-4B on image</span>
          </li>
          <li>
            <b>Fuse</b>
            <span>RRF, k = 10</span>
          </li>
          <li>
            <b>Rerank</b>
            <span>Cohere Rerank, top 50</span>
          </li>
          <li>
            <b>Answer</b>
            <span>DeepSeek V4.1 Flash, top 5, cited</span>
          </li>
          <li>
            <b>Grade</b>
            <span>nDCG@10 vs judged pages; answers vs reference</span>
          </li>
        </ol>
      </section>

      <section aria-labelledby="examples">
        <h2 id="examples" className="section-title">
          Examples
        </h2>
        <div className="tabs" role="tablist" aria-label="Examples">
          {showcase.map((s, i) => (
            <button
              key={s.query_id}
              role="tab"
              aria-selected={i === example}
              className={i === example ? 'on' : ''}
              onClick={() => setExample(i)}
            >
              {s.title}
            </button>
          ))}
        </div>
        <p className="example-note">
          {item.story}{' '}
          <a href={`#explore/q=${item.query_id}`}>Open in explorer →</a>
        </p>
        {error && <p className="error">{error}</p>}
        {detail && <Comparison detail={detail} configs={configs} meta={meta} />}
      </section>

      <section aria-labelledby="method">
        <h2 id="method" className="section-title">
          Method and limits
        </h2>
        <ul className="method">
          <li>Settings (RRF k, visual weight, rerank depth) tuned on 107 dev queries; all numbers on 211 held-out.</li>
          <li>±: half-width of the 95% bootstrap CI. Complete@5: all needed evidence in the top 5.</li>
          <li>Answers graded against reference answers by a DeepSeek model; 17/20 agreement with a hand check.</li>
          <li>Everything is precomputed; browsing makes no model calls.</li>
          <li>One corpus (14 EU labour-market reports, CC BY 4.0); other document types may rank differently.</li>
        </ul>
      </section>
    </article>
  )
}
