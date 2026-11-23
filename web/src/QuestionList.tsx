import { useMemo, useState } from 'react'
import type { QuestionSummary } from './api'

const CONTENT_TYPES = ['Table', 'Chart', 'Infographic', 'Text']

type Props = {
  questions: QuestionSummary[]
  selected: number | null
  onSelect: (id: number) => void
}

export function QuestionList({ questions, selected, onSelect }: Props) {
  const [search, setSearch] = useState('')
  const [contentType, setContentType] = useState<string | null>(null)

  const shown = useMemo(() => {
    const needle = search.trim().toLowerCase()
    return questions.filter(
      (q) =>
        (!needle || q.text.toLowerCase().includes(needle)) &&
        (!contentType || q.content_type.includes(contentType)),
    )
  }, [questions, search, contentType])

  return (
    <nav className="questions" aria-label="Benchmark questions">
      <input
        type="search"
        placeholder={`Search ${questions.length} questions`}
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        aria-label="Search questions"
      />
      <div className="chips" role="group" aria-label="Filter by content type">
        {CONTENT_TYPES.map((type) => (
          <button
            key={type}
            className={`chip ${contentType === type ? 'on' : ''}`}
            aria-pressed={contentType === type}
            onClick={() => setContentType(contentType === type ? null : type)}
          >
            {type}
          </button>
        ))}
      </div>
      <p className="muted small">{shown.length} shown</p>
      <ul>
        {shown.map((q) => (
          <li key={q.query_id}>
            <button className={`question ${q.query_id === selected ? 'on' : ''}`} onClick={() => onSelect(q.query_id)}>
              <span className="qid">Q{q.query_id}</span>
              <span className="qtext">{q.text}</span>
              <span className="qmeta">{q.content_type.join(' · ')}</span>
            </button>
          </li>
        ))}
      </ul>
    </nav>
  )
}
