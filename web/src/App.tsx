import { useCallback, useEffect, useMemo, useState } from 'react'
import { api, type Config, type Meta, type QuestionDetail, type QuestionSummary, type ShowcaseItem } from './api'
import { CostCalculator } from './CostCalculator'
import { Guide } from './Guide'
import { LaneColumn } from './LaneColumn'
import { PageViewer } from './PageViewer'
import { Privacy } from './Privacy'
import { QuestionList } from './QuestionList'
import { Scoreboard } from './Scoreboard'
import { Showcase } from './Showcase'

const MAX_LANES = 4
const VIEWS = [
  { id: 'explore', label: 'Explore' },
  { id: 'guide', label: 'Findings & guide' },
  { id: 'cost', label: 'Cost calculator' },
  { id: 'privacy', label: 'Privacy & deployment' },
] as const
type View = (typeof VIEWS)[number]['id']

// The URL hash keeps the view and question shareable: #explore/q=208, #guide, #cost, #privacy.
function readHash(): { view: View; question: number | null } {
  const hash = window.location.hash.slice(1)
  const view = (VIEWS.find((v) => hash.startsWith(v.id))?.id ?? 'explore') as View
  const match = hash.match(/q=(\d+)/)
  return { view, question: match ? Number(match[1]) : null }
}

export default function App() {
  const initial = readHash()
  const [view, setView] = useState<View>(initial.view)
  const [meta, setMeta] = useState<Meta | null>(null)
  const [configs, setConfigs] = useState<Map<string, Config>>(new Map())
  const [questions, setQuestions] = useState<QuestionSummary[]>([])
  const [showcase, setShowcase] = useState<ShowcaseItem[]>([])
  const [selected, setSelected] = useState<number | null>(initial.question)
  const [lanes, setLanes] = useState<string[]>([])
  const [detail, setDetail] = useState<QuestionDetail | null>(null)
  const [topK, setTopK] = useState(5)
  const [viewing, setViewing] = useState<number | null>(null)
  const [showAnswer, setShowAnswer] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([api.meta(), api.configs(), api.questions(), api.showcase()]).then(([m, c, q, s]) => {
      setMeta(m)
      setConfigs(new Map(c.map((x) => [x.id, x])))
      setQuestions(q)
      setShowcase(s)
      const story = s.find((item) => item.query_id === initial.question) ?? (initial.question === null ? s[0] : undefined)
      setSelected(initial.question ?? s[0].query_id)
      setLanes(story?.lanes ?? m.default_lanes)
    }, (e) => setError(String(e)))
    // Runs once on load; `initial` is read from the URL at that moment.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    window.location.hash = view === 'explore' && selected !== null ? `explore/q=${selected}` : view
  }, [view, selected])

  useEffect(() => {
    if (selected === null || !lanes.length) return
    api.question(selected, lanes).then(setDetail, (e) => setError(String(e)))
  }, [selected, lanes])

  useEffect(() => setShowAnswer(false), [selected])

  const laneConfigs = useMemo(() => lanes.map((id) => configs.get(id)).filter(Boolean) as Config[], [lanes, configs])
  const closeViewer = useCallback(() => setViewing(null), [])
  const replaceLane = (i: number, id: string) => setLanes(lanes.map((l, j) => (j === i ? id : l)))
  const addLane = () => setLanes([...lanes, 'bm25+voyage|vw1|cohere'])
  const pickStory = (item: ShowcaseItem) => {
    setSelected(item.query_id)
    setLanes(item.lanes)
  }

  if (error) return <p className="error page-error">Could not load the demo: {error}</p>
  if (!meta || !detail) return <p className="loading">Loading…</p>

  const q = detail.question
  const grades = new Map(q.judged.map((j) => [j.page_id, j.grade]))
  const story = showcase.find((item) => item.query_id === q.query_id)

  return (
    <div className="app">
      <header className="top">
        <div>
          <h1>Evidence Atlas</h1>
          <p className="muted">
            Which retrieval finds the evidence? {meta.questions} questions · {meta.pages.toLocaleString()} pages of EU
            labour-market reports · keyword, text, visual, and hybrid search compared on the same pages.
          </p>
        </div>
        <nav className="tabs" aria-label="Sections">
          {VIEWS.map((v) => (
            <button key={v.id} className={view === v.id ? 'on' : ''} aria-current={view === v.id ? 'page' : undefined} onClick={() => setView(v.id)}>
              {v.label}
            </button>
          ))}
        </nav>
      </header>

      {view === 'guide' && <Guide configs={configs} meta={meta} />}
      {view === 'cost' && <CostCalculator configs={configs} meta={meta} />}
      {view === 'privacy' && <Privacy />}

      {view === 'explore' && (
        <div className="layout">
          <QuestionList questions={questions} selected={selected} onSelect={setSelected} />

          <main>
            <Showcase items={showcase} selected={selected} onPick={pickStory} />

            <section className="question-card" aria-labelledby="question-title">
              <p className="small muted">
                Q{q.query_id} · {q.query_types.join(', ')} · evidence in: {q.content_type.join(', ')} · {q.judged.length}{' '}
                judged page{q.judged.length === 1 ? '' : 's'} · {q.partition === 'heldout' ? 'held-out' : 'dev'} question
              </p>
              <h2 id="question-title">{q.text}</h2>
              {story && (
                <p className="story-text">
                  <strong>{story.title}.</strong> {story.story}
                </p>
              )}
              <button className="link" onClick={() => setShowAnswer(!showAnswer)} aria-expanded={showAnswer}>
                {showAnswer ? 'Hide' : 'Show'} reference answer
              </button>
              {showAnswer && <p className="answer">{q.answer}</p>}
            </section>

            <div className="controls row">
              <div className="segmented" role="group" aria-label="Pages shown per lane">
                {[5, 10].map((k) => (
                  <button key={k} className={topK === k ? 'on' : ''} aria-pressed={topK === k} onClick={() => setTopK(k)}>
                    Top {k}
                  </button>
                ))}
              </div>
              <p className="legend small muted">
                <span className="mark-key g2">✓✓</span> complete answer <span className="mark-key g1">✓</span> partial evidence{' '}
                <span className="mark-key g0">✗</span> not relevant · click a page to inspect it
              </p>
              {lanes.length < MAX_LANES && (
                <button onClick={addLane} className="add">
                  + Add lane
                </button>
              )}
            </div>

            <div className="lanes">
              {detail.lanes.map((lane, i) => (
                <LaneColumn
                  key={`${i}-${lane.config}`}
                  lane={lane}
                  config={configs.get(lane.config)!}
                  configs={configs}
                  meta={meta}
                  topK={topK}
                  grades={grades}
                  onChange={(id) => replaceLane(i, id)}
                  onRemove={lanes.length > 1 ? () => setLanes(lanes.filter((_, j) => j !== i)) : undefined}
                  onOpenPage={(pageId) => setViewing(pageId)}
                />
              ))}
            </div>

            <Scoreboard lanes={laneConfigs} meta={meta} />
          </main>
        </div>
      )}

      {viewing !== null && (
        <PageViewer pageId={viewing} judged={q.judged.find((j) => j.page_id === viewing)} onClose={closeViewer} />
      )}
    </div>
  )
}
