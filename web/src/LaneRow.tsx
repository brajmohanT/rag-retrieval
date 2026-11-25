import { useState } from 'react'
import { KIND, laneName, type Config, type Lane, type Meta } from './api'
import { AnswerBox } from './AnswerBox'
import { LaneEditor } from './LaneEditor'
import { evidenceLine } from './words'

type Props = {
  lane: Lane
  config: Config
  configs: Map<string, Config>
  meta: Meta
  topK: number
  grades: Map<number, number>
  onOpenPage: (pageId: number) => void
  // Explorer only: swap or remove the setup.
  onChange?: (id: string) => void
  onRemove?: () => void
}

const GRADE = { 2: 'grade 2', 1: 'grade 1' } as Record<number, string>

// One setup on one question: ranked pages, then the answer generated from the top 5.
export function LaneRow({ lane, config, configs, meta, topK, grades, onOpenPage, onChange, onRemove }: Props) {
  const [editing, setEditing] = useState(false)
  const name = laneName(config)

  return (
    <section className="lane" aria-label={name}>
      <header className="lane-head">
        {/* Non-breaking hyphens keep model names like Voyage-mm-3.5 on one line. */}
        <h3>{name.replace(/-/g, '\u2011')}</h3>
        {config.members.length === 1 && <p className="lane-kind">{KIND[config.members[0]]}</p>}
        <p className="lane-metric">
          nDCG@10 {lane.metrics['ndcg@10'].toFixed(2)} · {evidenceLine(lane)}
        </p>
        {onChange && (
          <div className="lane-actions">
            <button className="link" onClick={() => setEditing(!editing)} aria-expanded={editing}>
              Change
            </button>
            {onRemove && (
              <button className="link" onClick={onRemove}>
                Remove
              </button>
            )}
          </div>
        )}
      </header>

      <div className="lane-body">
        {editing && onChange && (
          <LaneEditor current={config} configs={configs} meta={meta} onChange={onChange} onClose={() => setEditing(false)} />
        )}
        <ol className="strip" style={{ ['--k' as string]: topK }} aria-label={`Top ${topK} pages`}>
          {lane.pages.slice(0, topK).map((p) => (
            <li key={p.page_id}>
              <button
                className={`thumb${p.grade ? ' hit' : ''}`}
                onClick={() => onOpenPage(p.page_id)}
                aria-label={`Rank ${p.rank}, page ${p.page_id}${p.grade ? `, ${GRADE[p.grade]}` : ''}`}
              >
                <img src={`/page-images/${p.page_id}-thumb.webp`} alt="" loading="lazy" />
                <span className="thumb-rank">{p.rank}</span>
                {p.grade > 0 && <span className="thumb-hit" aria-hidden="true">✓</span>}
              </button>
            </li>
          ))}
        </ol>
        <AnswerBox answer={lane.answer} grades={grades} onOpenPage={onOpenPage} />
      </div>
    </section>
  )
}
