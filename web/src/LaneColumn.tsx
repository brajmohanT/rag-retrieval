import { useState } from 'react'
import { laneName, type Config, type Lane, type Meta } from './api'
import { LaneEditor } from './LaneEditor'

type Props = {
  lane: Lane
  config: Config
  configs: Map<string, Config>
  meta: Meta
  topK: number
  onChange: (id: string) => void
  onRemove?: () => void
  onOpenPage: (pageId: number, grade: number) => void
}

const GRADE = { 2: 'Complete answer', 1: 'Partial evidence' } as Record<number, string>

export function LaneColumn({ lane, config, configs, meta, topK, onChange, onRemove, onOpenPage }: Props) {
  const [editing, setEditing] = useState(false)
  const found = lane.pages.slice(0, topK).filter((p) => p.grade > 0).length
  const complete = topK === 5 ? lane.metrics['complete@5'] : null

  return (
    <section className="lane" aria-label={laneName(config, meta.presets)}>
      <header>
        <h3>{laneName(config, meta.presets)}</h3>
        <div className="row tight">
          <button className="link" onClick={() => setEditing(!editing)} aria-expanded={editing}>
            Change
          </button>
          {onRemove && (
            <button className="link" onClick={onRemove} aria-label="Remove lane">
              ✕
            </button>
          )}
        </div>
      </header>
      {editing && (
        <LaneEditor current={config} configs={configs} meta={meta} onChange={onChange} onClose={() => setEditing(false)} />
      )}
      <p className="lane-score">
        <strong>{found}</strong> relevant in top {topK}
        <span className="muted"> · nDCG@10 {lane.metrics['ndcg@10'].toFixed(2)}</span>
        {complete !== null && (
          <span className={`badge ${complete ? 'ok' : 'miss'}`}>{complete ? 'Enough to answer' : 'Not enough'}</span>
        )}
      </p>
      <ol className="pages">
        {lane.pages.slice(0, topK).map((p) => (
          <li key={p.page_id}>
            <button
              className={`page g${p.grade}`}
              onClick={() => onOpenPage(p.page_id, p.grade)}
              aria-label={`Rank ${p.rank}, page ${p.page_id}${p.grade ? `, ${GRADE[p.grade]}` : ', not judged relevant'}`}
            >
              <span className="rank">{p.rank}</span>
              <img src={`/page-images/${p.page_id}-thumb.webp`} alt="" loading="lazy" />
              <span className="mark">{p.grade === 2 ? '✓✓' : p.grade === 1 ? '✓' : '✗'}</span>
            </button>
          </li>
        ))}
      </ol>
    </section>
  )
}
