import { laneName, money, pct, seconds, type Config, type Meta } from './api'

type Props = { configs: Map<string, Config>; meta: Meta }

const KEYWORD = 'bm25|vw1'
const TEXT = 'dense|vw1'
const VOYAGE = 'voyage|vw1'
const COLQWEN = 'colqwen3|vw1'
const BEST = 'bm25+dense+voyage+colqwen3|vw1|cohere'
const FAST = 'bm25+voyage|vw1|cohere'
const OPEN = 'bm25+colqwen3|vw2' // open-weight models only, no proprietary reranker
const TABLE = [KEYWORD, TEXT, VOYAGE, COLQWEN, BEST, FAST]
const TYPES = ['Text', 'Table', 'Chart', 'Infographic']

// What we measured, turned into recommendations. Every number comes from the held-out questions.
export function Guide({ configs, meta }: Props) {
  const c = (id: string) => configs.get(id)!
  const ndcg = (id: string) => c(id).heldout['ndcg@10'].mean.toFixed(2)
  const tables = (id: string) => c(id).heldout_by_content_type.Table['ndcg@10'].toFixed(2)
  const answers = (id: string) => (c(id).answers ? pct(c(id).answers!.correct) : '–')
  const cards = [
    {
      need: 'Highest accuracy',
      setup: BEST,
      why: `Four retrievers fused, then Cohere reranks the top 50. ${pct(c(BEST).heldout['hit@5'].mean)} of questions have a relevant page in the top 5; ${answers(BEST)} of answers match the reference.`,
    },
    {
      need: 'Live use: fast and nearly as good',
      setup: FAST,
      why: `Keyword + one visual retriever + reranker matches the four-way fusion (nDCG ${ndcg(FAST)} vs ${ndcg(BEST)}) at about ${seconds(c(FAST).latency_p50_ms)} instead of ${seconds(c(BEST).latency_p50_ms)}. With a good reranker, a cheap first stage is enough.`,
    },
    {
      need: 'Reports full of tables and charts',
      setup: COLQWEN,
      why: `Keyword search scores ${tables(KEYWORD)} on table questions; visual retrieval alone scores ${tables(COLQWEN)}, and the best setup ${tables(BEST)}. Searching page images avoids depending on how well text was extracted.`,
    },
    {
      need: 'Lowest cost per question, no reranker',
      setup: VOYAGE,
      why: `One image embedding per page: nDCG ${ndcg(VOYAGE)} (keyword: ${ndcg(KEYWORD)}) at ${money(c(VOYAGE).query_cost_per_1k_usd)} per 1,000 questions and ${seconds(c(VOYAGE).latency_p50_ms)}.`,
    },
    {
      need: 'Data must stay in-house',
      setup: OPEN,
      selfHosted: true,
      why: `Keyword search plus ColQwen3, both runnable on your own servers (ColQwen3 is Apache-2.0): nDCG ${ndcg(OPEN)} here. The open Qwen3 reranker we tried added less than Cohere (+0.04 on dev, not significant), so expect a gap to the best setup unless a stronger self-hosted reranker is found.`,
    },
  ]

  return (
    <article className="page-article">
      <h2>Findings and a decision guide</h2>
      <p className="lede">
        We ran keyword, text-embedding, visual, and hybrid retrieval over the same {meta.pages.toLocaleString()} report pages and
        scored them on 211 held-out questions with human relevance labels. Settings were chosen on a separate set of 107
        questions, so these numbers were not tuned on the questions they report.
      </p>

      <h3>Five things we learned</h3>
      <ol className="findings">
        <li>
          <strong>Searching page images beats searching extracted text.</strong> Visual retrieval (ColQwen3) scores nDCG{' '}
          {ndcg(COLQWEN)} vs {ndcg(TEXT)} for text embeddings and {ndcg(KEYWORD)} for keyword search, and it wins on every
          content type, including plain text pages.
        </li>
        <li>
          <strong>Tables are where keyword search breaks.</strong> Table questions: {tables(KEYWORD)} for keyword vs{' '}
          {tables(BEST)} for the best setup. Tables can abbreviate (“FR” for France, “Nat.” for nationals), which keyword matching cannot bridge.
        </li>
        <li>
          <strong>Combining methods helps; a reranker helps most.</strong> Fusing all four retrievers reaches{' '}
          {ndcg('bm25+dense+voyage+colqwen3|vw1')}; adding a reranker reaches {ndcg(BEST)}.
        </li>
        <li>
          <strong>Better retrieval means better and safer answers.</strong> Answers matching the reference rise from{' '}
          {answers(KEYWORD)} (keyword) to {answers(BEST)}. With weak retrieval the model mostly declines rather than invents:{' '}
          {pct(c(KEYWORD).answers!.abstained)} declined vs {pct(c(BEST).answers!.abstained)}, while wrong answers stay near{' '}
          {pct(c(BEST).answers!.incorrect)}.
        </li>
        <li>
          <strong>Reading the page image did not improve answers here.</strong> Giving the answer model page images instead
          of extracted text changed accuracy by about one point on the 107 tuning questions, well within noise: on this corpus, finding the page mattered more than how it was read.
        </li>
      </ol>

      <h3>Which setup for which need</h3>
      <div className="cards">
        {cards.map((card) => {
          const cfg = c(card.setup)
          return (
            <section key={card.need} className="card">
              <p className="small muted">If you need</p>
              <h4>{card.need}</h4>
              <p className="card-setup">{laneName(cfg, meta.presets)}</p>
              <p className="small">{card.why}</p>
              <p className="card-stats small">
                {'selfHosted' in card
                  ? `nDCG ${ndcg(card.setup)} · self-hosted, so costs are GPU time rather than per-question fees`
                  : `nDCG ${ndcg(card.setup)} · ${money(cfg.query_cost_per_1k_usd)} / 1,000 questions · ${seconds(cfg.latency_p50_ms)}`}
              </p>
            </section>
          )
        })}
      </div>

      <h3>Quality by content type (nDCG@10, held-out)</h3>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th scope="col">Setup</th>
              {TYPES.map((t) => (
                <th key={t} scope="col">
                  {t} <span className="muted">(n={c(KEYWORD).heldout_by_content_type[t].n})</span>
                </th>
              ))}
              <th scope="col">All</th>
            </tr>
          </thead>
          <tbody>
            {TABLE.map((id) => (
              <tr key={id}>
                <th scope="row">{laneName(c(id), meta.presets)}</th>
                {TYPES.map((t) => {
                  const best = Math.max(...TABLE.map((x) => c(x).heldout_by_content_type[t]['ndcg@10']))
                  const v = c(id).heldout_by_content_type[t]['ndcg@10']
                  return (
                    <td key={t} className={v === best ? 'best-cell' : ''}>
                      {v.toFixed(3)}
                    </td>
                  )
                })}
                <td>{c(id).heldout['ndcg@10'].mean.toFixed(3)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="small muted">
        Green marks the best score per column; differences under about 0.03 are within noise. A question counts under every
        content type its evidence spans. Infographic results rest on 23 questions.
      </p>

      <h3>What this does and does not show</h3>
      <ul className="small">
        <li>One corpus: 14 EU labour-market reports. Contracts, manuals, or scanned forms may rank methods differently.</li>
        <li>Each comparison changes both the input (text or image) and the model, so gains belong to the whole approach, not to images alone.</li>
        <li>Answers are graded against reference answers by the answering model's family; a hand check agreed on 17 of 20.</li>
        <li>The reliable way to choose for your documents is to run this same evaluation on a sample of them.</li>
      </ul>
    </article>
  )
}
