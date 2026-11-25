import { useEffect, useState } from 'react'
import { api, type Config, type Meta, type QuestionSummary, type ShowcaseItem } from './api'
import { Explore } from './Explore'
import { Overview } from './Overview'

type View = 'overview' | 'explore'

// #explore/q=208 opens the explorer on a query; anything else is the overview.
function parseHash(hash: string): { view: View; question: number | null } {
  const match = hash.match(/q=(\d+)/)
  return { view: hash.startsWith('#explore') ? 'explore' : 'overview', question: match ? Number(match[1]) : null }
}

export default function App() {
  const [route, setRoute] = useState(() => parseHash(window.location.hash))
  const [meta, setMeta] = useState<Meta | null>(null)
  const [configs, setConfigs] = useState<Map<string, Config>>(new Map())
  const [questions, setQuestions] = useState<QuestionSummary[]>([])
  const [showcase, setShowcase] = useState<ShowcaseItem[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([api.meta(), api.configs(), api.questions(), api.showcase()]).then(([m, c, q, s]) => {
      setMeta(m)
      setConfigs(new Map(c.map((x) => [x.id, x])))
      setQuestions(q)
      setShowcase(s)
    }, (e) => setError(String(e)))
  }, [])

  useEffect(() => {
    const onHash = () => {
      const next = parseHash(window.location.hash)
      setRoute((prev) => {
        if (next.view !== prev.view) window.scrollTo({ top: 0 })
        return next
      })
    }
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  if (error) return <p className="error page-error">Could not load the demo: {error}</p>
  if (!meta) return <p className="loading page-loading">Loading…</p>

  return (
    <div className="app">
      <header className="site-header">
        <a className="wordmark" href="#">
          retrieval in rag
        </a>
        <nav aria-label="Sections">
          <a href="#" aria-current={route.view === 'overview' ? 'page' : undefined}>
            Overview
          </a>
          <a href="#explore" aria-current={route.view === 'explore' ? 'page' : undefined}>
            Explorer
          </a>
        </nav>
      </header>

      <div className="content">
        {route.view === 'overview' ? (
          <Overview configs={configs} meta={meta} showcase={showcase} />
        ) : (
          <Explore
            questions={questions}
            showcase={showcase}
            selected={route.question ?? showcase[0].query_id}
            configs={configs}
            meta={meta}
            go={(hash) => (window.location.hash = hash)}
          />
        )}
      </div>
    </div>
  )
}
