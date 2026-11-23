import type { ShowcaseItem } from './api'

type Props = { items: ShowcaseItem[]; selected: number | null; onPick: (item: ShowcaseItem) => void }

// Hand-picked questions that each tell one story in a few seconds.
export function Showcase({ items, selected, onPick }: Props) {
  return (
    <section className="showcase" aria-labelledby="showcase-title">
      <h2 id="showcase-title" className="small muted">Start here: six questions, six lessons</h2>
      <ol>
        {items.map((item, i) => (
          <li key={item.query_id}>
            <button className={`story ${item.query_id === selected ? 'on' : ''}`} onClick={() => onPick(item)}>
              <span className="story-n">{i + 1}</span>
              <span className="story-title">{item.title}</span>
            </button>
          </li>
        ))}
      </ol>
    </section>
  )
}
