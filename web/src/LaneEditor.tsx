import { useState } from 'react'
import { RETRIEVER_ORDER, VISUAL, configId, type Config, type Meta } from './api'

type Props = {
  current: Config
  configs: Map<string, Config>
  meta: Meta
  onChange: (id: string) => void
  onClose: () => void
}

// Choose a named preset, or build any of the 66 precomputed setups.
export function LaneEditor({ current, configs, meta, onChange, onClose }: Props) {
  const [members, setMembers] = useState<string[]>(current.members)
  const [weight, setWeight] = useState(current.visual_weight)
  const [rerank, setRerank] = useState(current.rerank)
  const mixed = members.some((m) => VISUAL.has(m)) && members.some((m) => !VISUAL.has(m))
  const id = members.length ? configId(members, weight, rerank) : null
  const valid = id !== null && configs.has(id)

  const toggle = (m: string) => setMembers(members.includes(m) ? members.filter((x) => x !== m) : [...members, m])

  return (
    <div className="editor" role="dialog" aria-label="Change retrieval setup">
      <label className="small">
        Preset
        <select value="" onChange={(e) => e.target.value && (onChange(e.target.value), onClose())}>
          <option value="">Choose a preset…</option>
          {meta.presets.map((p) => (
            <option key={p.config} value={p.config}>
              {p.name}
            </option>
          ))}
        </select>
      </label>
      <fieldset>
        <legend className="small">Retrievers (2 or more are fused)</legend>
        {RETRIEVER_ORDER.map((m) => (
          <label key={m} className="check">
            <input type="checkbox" checked={members.includes(m)} onChange={() => toggle(m)} />
            {meta.retrievers[m]}
          </label>
        ))}
      </fieldset>
      {mixed && (
        <fieldset>
          <legend className="small">Weight of visual retrievers</legend>
          {[0.5, 1, 2].map((w) => (
            <label key={w} className="check inline">
              <input type="radio" name="weight" checked={weight === w} onChange={() => setWeight(w)} />×{w}
            </label>
          ))}
        </fieldset>
      )}
      <label className="check">
        <input type="checkbox" checked={rerank} onChange={(e) => setRerank(e.target.checked)} />
        Rerank top 50 (Cohere Rerank 5)
      </label>
      <div className="row">
        <button className="primary" disabled={!valid} onClick={() => (onChange(id!), onClose())}>
          Apply
        </button>
        <button onClick={onClose}>Cancel</button>
      </div>
    </div>
  )
}
