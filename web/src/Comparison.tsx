import { useCallback, useEffect, useState, type ReactNode } from 'react'
import type { Config, Meta, QuestionDetail } from './api'
import { LaneRow } from './LaneRow'
import { PageViewer } from './PageViewer'

type Props = {
  detail: QuestionDetail
  configs: Map<string, Config>
  meta: Meta
  topK?: number
  controls?: ReactNode
  // Explorer only.
  onChangeLane?: (index: number, id: string) => void
  onRemoveLane?: (index: number) => void
}

// A query, then one row per setup: its ranked pages and the cited answer from its top 5.
export function Comparison({ detail, configs, meta, topK = 5, controls, onChangeLane, onRemoveLane }: Props) {
  const [viewing, setViewing] = useState<number | null>(null)
  const [showAnswer, setShowAnswer] = useState(false)
  const closeViewer = useCallback(() => setViewing(null), [])
  const q = detail.question
  const grades = new Map(q.judged.map((j) => [j.page_id, j.grade]))

  useEffect(() => setShowAnswer(false), [q.query_id])

  return (
    <>
      <section className="question-card" aria-labelledby="question-text">
        <h3 id="question-text" className="question-text">
          {q.text}
        </h3>
        <p className="question-meta">
          Q{q.query_id} · evidence: {q.content_type.join(', ').toLowerCase()} · {q.judged.length} judged page
          {q.judged.length === 1 ? '' : 's'} · {q.partition === 'heldout' ? 'held-out' : 'dev'} ·{' '}
          <button className="link" onClick={() => setShowAnswer(!showAnswer)} aria-expanded={showAnswer}>
            {showAnswer ? 'hide' : 'show'} reference answer
          </button>
        </p>
        {showAnswer && <p className="reference">{q.answer}</p>}
      </section>

      {controls && <div className="lanes-intro">{controls}</div>}

      <div className="lanes">
        {detail.lanes.map((lane, i) => (
          <LaneRow
            key={`${i}-${lane.config}`}
            lane={lane}
            config={configs.get(lane.config)!}
            configs={configs}
            meta={meta}
            topK={topK}
            grades={grades}
            onOpenPage={setViewing}
            onChange={onChangeLane && ((id) => onChangeLane(i, id))}
            onRemove={onRemoveLane && detail.lanes.length > 1 ? () => onRemoveLane(i) : undefined}
          />
        ))}
      </div>

      {viewing !== null && (
        <PageViewer pageId={viewing} judged={q.judged.find((j) => j.page_id === viewing)} onClose={closeViewer} />
      )}
    </>
  )
}
