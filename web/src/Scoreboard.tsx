import { useState } from 'react'
import { laneName, money, pct, seconds, type Config } from './api'

type Props = { lanes: Config[] }

const TYPES = ['Text', 'Table', 'Chart', 'Infographic']

// Held-out results: overall metrics, or nDCG@10 split by the content type holding the evidence.
export function Scoreboard({ lanes }: Props) {
  const [byType, setByType] = useState(false)
  if (!lanes.length) return null
  const ceiling = lanes[0].ceiling
  const best = (f: (c: Config) => number) => Math.max(...lanes.map(f))
  // Bolds the best value in its column, and any within 0.005 of it (ties for practical purposes).
  const cell = (key: string, f: (c: Config) => number, c: Config, text: string) => (
    <td key={key} className={lanes.length > 1 && best(f) - f(c) < 0.005 ? 'best-cell' : ''}>
      {text}
    </td>
  )

  const ndcg = (c: Config) => c.heldout['ndcg@10'].mean
  const recall = (c: Config) => c.heldout['recall@5'].mean
  const complete = (c: Config) => c.heldout['complete@5'].mean
  const correct = (c: Config) => c.answers?.correct ?? -1
  const typed = (t: string) => (c: Config) => c.heldout_by_content_type[t]?.['ndcg@10'] ?? -1

  return (
    <div className="scoreboard">
      <div className="segmented" role="group" aria-label="Table view">
        <button className={byType ? '' : 'on'} aria-pressed={!byType} onClick={() => setByType(false)}>
          Overall
        </button>
        <button className={byType ? 'on' : ''} aria-pressed={byType} onClick={() => setByType(true)}>
          nDCG@10 by content type
        </button>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            {byType ? (
              <tr>
                <th scope="col">Setup</th>
                {TYPES.map((t) => (
                  <th key={t} scope="col">
                    {t} <span className="muted">n={lanes[0].heldout_by_content_type[t]?.n}</span>
                  </th>
                ))}
              </tr>
            ) : (
              <tr>
                <th scope="col">Setup</th>
                <th scope="col">nDCG@10</th>
                <th scope="col">Recall@5</th>
                <th scope="col">Complete@5 <span className="muted">max {pct(ceiling['complete@5'])}</span></th>
                <th scope="col">Answer acc.</th>
                <th scope="col">$ / 1k q</th>
                <th scope="col">p50</th>
              </tr>
            )}
          </thead>
          <tbody>
            {lanes.map((c) => (
              <tr key={c.id}>
                <th scope="row">{laneName(c)}</th>
                {byType ? (
                  TYPES.map((t) => cell(t, typed(t), c, typed(t)(c).toFixed(3)))
                ) : (
                  <>
                    {cell('ndcg', ndcg, c, `${ndcg(c).toFixed(3)} ±${((c.heldout['ndcg@10'].high - c.heldout['ndcg@10'].low) / 2).toFixed(3)}`)}
                    {cell('recall', recall, c, recall(c).toFixed(3))}
                    {cell('complete', complete, c, pct(complete(c)))}
                    {cell('correct', correct, c, c.answers ? pct(c.answers.correct) : '–')}
                    <td>{money(c.query_cost_per_1k_usd)}</td>
                    <td>{seconds(c.latency_p50_ms)}</td>
                  </>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
