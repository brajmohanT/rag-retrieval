import { useState } from 'react'
import { laneName, money, seconds, type Config, type Meta } from './api'

type Props = { configs: Map<string, Config>; meta: Meta }

const ANSWER_FALLBACK = 'bm25+dense+voyage+colqwen3|vw1|cohere' // answer cost for setups without precomputed answers

function bytes(n: number) {
  if (n < 1e9) return `${(n / 1e6).toFixed(n < 1e7 ? 1 : 0)} MB`
  return `${(n / 1e9).toFixed(1)} GB`
}

// Scale the per-page and per-question costs we measured to a client's volume.
export function CostCalculator({ configs, meta }: Props) {
  const [pages, setPages] = useState(10000)
  const [questions, setQuestions] = useState(5000)
  const [setup, setSetup] = useState('bm25+voyage|vw1|cohere')
  const [withAnswers, setWithAnswers] = useState(true)

  const config = configs.get(setup)!
  const perPage = config.index_cost_usd / meta.pages
  const indexing = perPage * pages
  const retrieval = (config.query_cost_per_1k_usd / 1000) * questions
  const answerPer1k = (config.answers ?? configs.get(ANSWER_FALLBACK)!.answers)?.cost_per_1k_usd ?? 0
  const answering = withAnswers ? (answerPer1k / 1000) * questions : 0
  const storage = config.members.reduce((sum, m) => sum + (meta.vector_bytes_per_page[m] ?? 0), 0) * pages

  return (
    <article className="page-article">
      <h2>Cost calculator</h2>
      <p className="lede">
        Estimates scaled from what this demo actually paid at API list prices (November 2026). They cover model API calls only.
      </p>

      <form className="calc" onSubmit={(e) => e.preventDefault()}>
        <label>
          Pages to index
          <input type="number" min={1} step={1000} value={pages} onChange={(e) => setPages(Math.max(0, Number(e.target.value)))} />
        </label>
        <label>
          Questions per month
          <input
            type="number"
            min={0}
            step={1000}
            value={questions}
            onChange={(e) => setQuestions(Math.max(0, Number(e.target.value)))}
          />
        </label>
        <label>
          Setup
          <select value={setup} onChange={(e) => setSetup(e.target.value)}>
            {meta.presets.map((p) => (
              <option key={p.config} value={p.config}>
                {p.name}
              </option>
            ))}
          </select>
        </label>
        <label className="check">
          <input type="checkbox" checked={withAnswers} onChange={(e) => setWithAnswers(e.target.checked)} />
          Generate a cited answer for each question
        </label>
      </form>

      <div className="cards results">
        <section className="card">
          <p className="small muted">One-time indexing</p>
          <p className="big">{money(indexing)}</p>
          <p className="small muted">{money(perPage * 1000)} per 1,000 pages. Repeated whenever you change embedding model.</p>
        </section>
        <section className="card">
          <p className="small muted">Per month</p>
          <p className="big">{money(retrieval + answering)}</p>
          <p className="small muted">
            Retrieval {money(retrieval)}
            {withAnswers && <> + answers {money(answering)}</>}
          </p>
        </section>
        <section className="card">
          <p className="small muted">Vector storage</p>
          <p className="big">{storage ? bytes(storage) : '—'}</p>
          <p className="small muted">
            {config.members.includes('colqwen3')
              ? 'Multi-vector pages (~750 vectors each) dominate; storing them in 16-bit halves this.'
              : 'Single vector per page. Keyword search adds an inverted index roughly the size of the text.'}
          </p>
        </section>
        <section className="card">
          <p className="small muted">Response time (median)</p>
          <p className="big">{seconds(config.latency_p50_ms + (withAnswers ? 2800 : 0))}</p>
          <p className="small muted">Retrieval {seconds(config.latency_p50_ms)}{withAnswers && ' + answer ~2.8 s'}</p>
        </section>
      </div>

      <h3>Not included</h3>
      <ul className="small">
        <li>Hosting, databases, and engineering time.</li>
        <li>Turning PDFs into text and page images: this corpus came with extracted text, which a real deployment must produce.</li>
        <li>Volume discounts, committed-use pricing, or self-hosting, which changes API costs into GPU costs.</li>
      </ul>
      <p className="small muted">
        Setup shown: {laneName(config, meta.presets)}. Answer cost uses DeepSeek V4.1 Flash, measured at{' '}
        {money(answerPer1k)} per 1,000 answers{config.answers ? '' : ' (from the best preset, as this setup has no answers)'}.
      </p>
    </article>
  )
}
