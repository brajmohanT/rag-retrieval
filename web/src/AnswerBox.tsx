import type { Answer } from './api'

type Props = {
  answer: Answer | null
  grades: Map<number, number>
  onOpenPage: (pageId: number) => void
}

const CITATION = /\[p(\d+)\]/g
const VERDICT: Record<Answer['verdict'], { label: string; tone: string }> = {
  CORRECT: { label: 'Matches reference', tone: 'ok' },
  PARTIAL: { label: 'Partly matches reference', tone: 'partial' },
  INCORRECT: { label: 'Does not match reference', tone: 'miss' },
  ABSTAINED: { label: 'Declined: not enough evidence', tone: 'neutral' },
  UNPARSED: { label: 'Not graded', tone: 'neutral' },
}

// The lane's generated answer, with each [p123] citation as a button that opens the cited page.
export function AnswerBox({ answer, grades, onOpenPage }: Props) {
  if (!answer) {
    return <p className="answer-box muted small">Answers are precomputed for the preset setups only.</p>
  }
  const pieces: (string | number)[] = []
  let last = 0
  for (const match of answer.text.matchAll(CITATION)) {
    pieces.push(answer.text.slice(last, match.index), Number(match[1]))
    last = match.index! + match[0].length
  }
  pieces.push(answer.text.slice(last))
  const verdict = VERDICT[answer.verdict]

  return (
    <div className="answer-box">
      <p className="small muted">
        Answer from the top 5 pages (DeepSeek V4.1 Flash, page text)
        <span className={`badge ${verdict.tone}`}>{verdict.label}</span>
      </p>
      <p>
        {pieces.map((piece, i) =>
          typeof piece === 'number' ? (
            <button
              key={i}
              className={`cite g${grades.get(piece) ?? 0}`}
              onClick={() => onOpenPage(piece)}
              title={grades.get(piece) ? 'Cites a page judged relevant' : 'Cites a page not judged relevant'}
            >
              p{piece}
            </button>
          ) : (
            <span key={i}>{piece}</span>
          ),
        )}
      </p>
    </div>
  )
}
