import { useEffect, useMemo, useState } from 'react'
import { api, type Config, type Meta, type QuestionDetail, type QuestionSummary, type ShowcaseItem } from './api'
import { Comparison } from './Comparison'
import { QuestionList } from './QuestionList'
import { Scoreboard } from './Scoreboard'
import { FAST } from './words'

const MAX_LANES = 4

type Props = {
  questions: QuestionSummary[]
  showcase: ShowcaseItem[]
  selected: number
  configs: Map<string, Config>
  meta: Meta
  go: (hash: string) => void
}

// Every benchmark question, with up to four setups side by side and any of the 66 setups selectable.
export function Explore({ questions, showcase, selected, configs, meta, go }: Props) {
  const [lanes, setLanes] = useState<string[]>(() => showcase.find((s) => s.query_id === selected)?.lanes ?? meta.default_lanes)
  const [detail, setDetail] = useState<QuestionDetail | null>(null)
  const [topK, setTopK] = useState(5)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.question(selected, lanes).then(setDetail, (e) => setError(String(e)))
  }, [selected, lanes])

  const laneConfigs = useMemo(() => lanes.map((id) => configs.get(id)).filter(Boolean) as Config[], [lanes, configs])

  const controls = (
    <div className="row">
      <div className="segmented" role="group" aria-label="Pages shown per setup">
        {[5, 10].map((k) => (
          <button key={k} className={topK === k ? 'on' : ''} aria-pressed={topK === k} onClick={() => setTopK(k)}>
            Top {k}
          </button>
        ))}
      </div>
      {lanes.length < MAX_LANES && (
        <button className="add" onClick={() => setLanes([...lanes, FAST])}>
          + Add setup
        </button>
      )}
    </div>
  )

  return (
    <div className="explore">
      <QuestionList questions={questions} selected={selected} onSelect={(id) => go(`explore/q=${id}`)} />
      <main className="explore-main">
        <p className="recorded-note">
          Recorded results · {meta.questions} benchmark questions · {meta.configs} setups
        </p>
        {error && <p className="error">Could not load this question: {error}</p>}
        {detail && (
          <Comparison
            detail={detail}
            configs={configs}
            meta={meta}
            topK={topK}
            controls={controls}
            onChangeLane={(i, id) => setLanes(lanes.map((l, j) => (j === i ? id : l)))}
            onRemoveLane={(i) => setLanes(lanes.filter((_, j) => j !== i))}
          />
        )}
        <h2 className="section-title">These setups on all 211 held-out queries</h2>
        <Scoreboard lanes={laneConfigs} />
      </main>
    </div>
  )
}
