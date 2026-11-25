// Setup IDs used across the overview, and how a lane did on one question.
import type { Answer, Lane } from './api'

export const KEYWORD = 'bm25|vw1'
export const TEXT = 'dense|vw1'
export const VOYAGE = 'voyage|vw1'
export const COLQWEN = 'colqwen3|vw1'
export const HYBRID = 'bm25+dense+voyage+colqwen3|vw1'
export const BEST = 'bm25+dense+voyage+colqwen3|vw1|cohere'
export const FAST = 'bm25+voyage|vw1|cohere'
export const PRESETS = [KEYWORD, TEXT, VOYAGE, COLQWEN, HYBRID, FAST, BEST]

export const VERDICT: Record<Answer['verdict'], { label: string; tone: 'ok' | 'partial' | 'wrong' | 'neutral' }> = {
  CORRECT: { label: 'Correct', tone: 'ok' },
  PARTIAL: { label: 'Partial', tone: 'partial' },
  INCORRECT: { label: 'Wrong', tone: 'wrong' },
  ABSTAINED: { label: 'Abstained', tone: 'neutral' },
  UNPARSED: { label: 'Not graded', tone: 'neutral' },
}

// Rank of the first judged page; the answer model reads the top 5.
export function evidenceLine(lane: Lane): string {
  const first = lane.pages.find((p) => p.grade > 0)
  if (!first) return `no relevant page in top ${lane.pages.length}`
  return `first relevant @${first.rank}${first.rank > 5 ? ' (outside top 5)' : ''}`
}
