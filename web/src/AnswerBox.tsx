import type { Answer } from './api'
import { VERDICT } from './words'

type Props = {
  answer: Answer | null
  grades: Map<number, number>
  onOpenPage: (pageId: number) => void
}

const CITATION = /\[p(\d+)\]/g
const BOLD = /\*\*(.+?)\*\*/g

// The model writes Markdown bold (**73%**); show it as bold rather than as asterisks.
function withBold(text: string, key: number) {
  const parts = text.split(BOLD)
  return <span key={key}>{parts.map((part, i) => (i % 2 ? <strong key={i}>{part}</strong> : part))}</span>
}

// The lane's generated answer, with each [p123] citation as a button that opens the cited page.
export function AnswerBox({ answer, grades, onOpenPage }: Props) {
  if (!answer) {
    return <p className="answer-none">No answer generated for this setup.</p>
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
      <p className={`verdict ${verdict.tone}`}>{verdict.label}</p>
      <p className="answer-text">
        {pieces.map((piece, i) =>
          typeof piece === 'number' ? (
            <button
              key={i}
              className={`cite${grades.get(piece) ? ' hit' : ''}`}
              onClick={() => onOpenPage(piece)}
              title={grades.get(piece) ? 'Cites a page marked as evidence' : 'Cites a page not marked as evidence'}
            >
              p{piece}
            </button>
          ) : (
            withBold(piece, i)
          ),
        )}
      </p>
    </div>
  )
}
