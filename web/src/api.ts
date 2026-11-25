// Types and fetchers for the demo backend (src/evidence_atlas/api/app.py).

export type Stat = { mean: number; low: number; high: number }

export type Config = {
  id: string
  members: string[]
  visual_weight: number
  rerank: boolean
  index_cost_usd: number
  query_cost_per_1k_usd: number
  latency_p50_ms: number
  heldout: Record<string, Stat>
  heldout_by_content_type: Record<string, { n: number; 'ndcg@10': number; 'complete@5': number }>
  ceiling: Record<string, number>
  answers: AnswerStats | null
}

export type AnswerStats = {
  n: number
  correct: number
  partial: number
  incorrect: number
  abstained: number
  cites_judged_page: number
  cost_per_1k_usd: number
}

export type Answer = {
  text: string
  cited: number[]
  invalid_citations: number[]
  abstained: boolean
  verdict: 'CORRECT' | 'PARTIAL' | 'INCORRECT' | 'ABSTAINED' | 'UNPARSED'
  pages: number[]
  cites_judged_page: boolean
}

export type Meta = {
  retrievers: Record<string, string>
  presets: { name: string; config: string }[]
  default_lanes: string[]
  questions: number
  configs: number
  pages: number
  vector_bytes_per_page: Record<string, number>
}

export type ShowcaseItem = { query_id: number; title: string; story: string; lanes: string[] }

export type QuestionSummary = {
  query_id: number
  text: string
  partition: 'dev' | 'heldout'
  query_types: string[]
  content_type: string[]
  judged: number
}

export type JudgedPage = { page_id: number; grade: number; boxes: number[][] }

export type Lane = {
  config: string
  metrics: Record<string, number>
  pages: { page_id: number; rank: number; grade: number }[]
  answer: Answer | null
}

export type QuestionDetail = {
  question: QuestionSummary & { answer: string; judged: JudgedPage[] }
  lanes: Lane[]
}

export type Page = {
  page_id: number
  doc_id: string
  pdf_page: number
  markdown: string
  width: number
  height: number
  license: string
  url: string
  doc_year: number
  thumb: string
  image: string
}

// Built with VITE_STATIC=1 (uv run atlas-export-static), the site reads the exported JSON files instead of
// calling the backend. All URLs are relative to the build's base, so the static site works under a sub-path.
const STATIC = import.meta.env.VITE_STATIC === '1'

export const asset = (path: string) => import.meta.env.BASE_URL + path.replace(/^\//, '')
export const thumbUrl = (pageId: number) => asset(`page-images/${pageId}-thumb.webp`)

async function get<T>(path: string): Promise<T> {
  const url = asset(STATIC ? `${path}.json` : path)
  const response = await fetch(url)
  if (!response.ok) throw new Error(`${url}: ${response.status} ${await response.text()}`)
  return response.json()
}

// A static question file holds lanes for every configuration; keep the requested ones, in order.
async function staticQuestion(id: number, lanes: string[]): Promise<QuestionDetail> {
  const detail = await get<QuestionDetail>(`api/questions/${id}`)
  const wanted = lanes.length ? lanes : (await api.meta()).default_lanes
  const byConfig = new Map(detail.lanes.map((lane) => [lane.config, lane]))
  const unknown = wanted.filter((c) => !byConfig.has(c))
  if (unknown.length) throw new Error(`Unknown configuration(s): ${unknown.join(', ')}`)
  return { ...detail, lanes: wanted.map((c) => byConfig.get(c)!) }
}

export const api = {
  meta: () => get<Meta>('api/meta'),
  configs: () => get<Config[]>('api/configs'),
  questions: () => get<QuestionSummary[]>('api/questions'),
  question: (id: number, lanes: string[]) =>
    STATIC
      ? staticQuestion(id, lanes)
      : get<QuestionDetail>(`api/questions/${id}?configs=${lanes.map(encodeURIComponent).join(',')}`),
  page: (id: number) =>
    get<Page>(`api/pages/${id}`).then((p) => ({ ...p, thumb: asset(p.thumb), image: asset(p.image) })),
  showcase: () => get<ShowcaseItem[]>('api/showcase'),
}

// Configuration IDs look like "bm25+voyage|vw0.5|cohere".
export const RETRIEVER_ORDER = ['bm25', 'dense', 'voyage', 'colqwen3']
export const VISUAL = new Set(['voyage', 'colqwen3'])

export function configId(members: string[], visualWeight: number, rerank: boolean): string {
  const ordered = RETRIEVER_ORDER.filter((m) => members.includes(m))
  const mixed = ordered.some((m) => VISUAL.has(m)) && ordered.some((m) => !VISUAL.has(m))
  return `${ordered.join('+')}|vw${mixed ? visualWeight : 1}${rerank ? '|cohere' : ''}`
}

export const SHORT: Record<string, string> = { bm25: 'BM25', dense: 'Qwen3-Emb-8B', voyage: 'Voyage-mm-3.5', colqwen3: 'ColQwen3-4B' }
export const KIND: Record<string, string> = {
  bm25: 'text · lexical',
  dense: 'text · dense',
  voyage: 'image · single-vector',
  colqwen3: 'image · multi-vector',
}

// "BM25", "RRF(BM25, Voyage-mm-3.5) → rerank", "RRF(all 4, visual ×2)".
export function laneName(config: Config): string {
  if (config.members.length === 1) return SHORT[config.members[0]]
  const inner = config.members.length === 4 ? ['all 4'] : config.members.map((m) => SHORT[m])
  if (config.visual_weight !== 1) inner.push(`visual ×${config.visual_weight}`)
  return `RRF(${inner.join(', ')})${config.rerank ? ' → rerank' : ''}`
}

export const pct = (x: number) => `${Math.round(x * 100)}%`
export const money = (x: number) => (x === 0 ? '$0' : x < 0.01 ? '<$0.01' : `$${x.toFixed(2)}`)
export const seconds = (ms: number) => (ms < 1000 ? `${Math.round(ms)} ms` : `${(ms / 1000).toFixed(1)} s`)
