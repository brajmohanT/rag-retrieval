import { laneName, type Config, type Meta } from './api'

type Props = { lanes: Config[]; meta: Meta }

const pct = (x: number) => `${Math.round(x * 100)}%`
const money = (x: number) => (x === 0 ? '$0' : x < 0.01 ? '<$0.01' : `$${x.toFixed(2)}`)
const seconds = (ms: number) => (ms < 1000 ? `${Math.round(ms)} ms` : `${(ms / 1000).toFixed(1)} s`)

// Held-out results for the setups in the lanes: quality, cost, and speed side by side.
export function Scoreboard({ lanes, meta }: Props) {
  if (!lanes.length) return null
  const best = Math.max(...lanes.map((c) => c.heldout['ndcg@10'].mean))
  const ceiling = lanes[0].ceiling
  return (
    <section className="scoreboard" aria-labelledby="scoreboard-title">
      <h2 id="scoreboard-title">How each setup does across all 211 held-out questions</h2>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th scope="col">Setup</th>
              <th scope="col">nDCG@10</th>
              <th scope="col">Right page in top 5</th>
              <th scope="col">Enough to answer in top 5</th>
              <th scope="col">Tables nDCG</th>
              <th scope="col">Answers matching reference</th>
              <th scope="col">Cost / 1,000 questions</th>
              <th scope="col">Latency (p50)</th>
            </tr>
          </thead>
          <tbody>
            {lanes.map((c) => {
              const ndcg = c.heldout['ndcg@10']
              return (
                <tr key={c.id} className={ndcg.mean === best ? 'best' : ''}>
                  <th scope="row">{laneName(c, meta.presets)}</th>
                  <td>
                    <span className="bar" style={{ ['--w' as string]: pct(ndcg.mean) }} />
                    {ndcg.mean.toFixed(3)}
                    <span className="muted small"> ±{((ndcg.high - ndcg.low) / 2).toFixed(3)}</span>
                  </td>
                  <td>{pct(c.heldout['hit@5'].mean)}</td>
                  <td>
                    {pct(c.heldout['complete@5'].mean)}
                    <span className="muted small"> of {pct(ceiling['complete@5'])} possible</span>
                  </td>
                  <td>{c.heldout_by_content_type.Table?.['ndcg@10'].toFixed(3) ?? '–'}</td>
                  <td>
                    {c.answers ? (
                      <>
                        {pct(c.answers.correct)}
                        <span className="muted small"> +{pct(c.answers.partial)} partly</span>
                      </>
                    ) : (
                      '–'
                    )}
                  </td>
                  <td>{money(c.query_cost_per_1k_usd)}</td>
                  <td>{seconds(c.latency_p50_ms)}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      <p className="small muted">
        ± is half the 95% bootstrap interval. “Enough to answer”: a complete-answer page, or every partial page, is in the top
        5; some questions have more evidence pages than fit, hence the ceiling. Latency is the API-call median; reranking adds to
        retrieval time. Answers are graded against the dataset's reference answers by the same model (DeepSeek), so treat them as
        indicative; – means no precomputed answers for that setup.
      </p>
    </section>
  )
}
