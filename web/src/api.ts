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
}

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

async function get<T>(path: string): Promise<T> {
  const response = await fetch(path)
  if (!response.ok) throw new Error(`${path}: ${response.status} ${await response.text()}`)
  return response.json()
}

export const api = {
  meta: () => get<Meta>('/api/meta'),
  configs: () => get<Config[]>('/api/configs'),
  questions: () => get<QuestionSummary[]>('/api/questions'),
  question: (id: number, lanes: string[]) =>
    get<QuestionDetail>(`/api/questions/${id}?configs=${lanes.map(encodeURIComponent).join(',')}`),
  page: (id: number) => get<Page>(`/api/pages/${id}`),
}

// Configuration IDs look like "bm25+voyage|vw0.5|cohere".
export const RETRIEVER_ORDER = ['bm25', 'dense', 'voyage', 'colqwen3']
export const VISUAL = new Set(['voyage', 'colqwen3'])

export function configId(members: string[], visualWeight: number, rerank: boolean): string {
  const ordered = RETRIEVER_ORDER.filter((m) => members.includes(m))
  const mixed = ordered.some((m) => VISUAL.has(m)) && ordered.some((m) => !VISUAL.has(m))
  return `${ordered.join('+')}|vw${mixed ? visualWeight : 1}${rerank ? '|cohere' : ''}`
}

const SHORT: Record<string, string> = { bm25: 'BM25', dense: 'Text emb.', voyage: 'Voyage', colqwen3: 'ColQwen3' }

export function laneName(config: Config, presets: Meta['presets']): string {
  const preset = presets.find((p) => p.config === config.id)
  if (preset) return preset.name
  const parts = [config.members.map((m) => SHORT[m]).join(' + ')]
  if (config.visual_weight !== 1) parts.push(`visual ×${config.visual_weight}`)
  if (config.rerank) parts.push('rerank')
  return parts.join(' · ')
}
