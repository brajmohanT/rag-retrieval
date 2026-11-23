import { useEffect, useState } from 'react'
import { api, type JudgedPage, type Page } from './api'

type Props = {
  pageId: number
  judged: JudgedPage | undefined
  onClose: () => void
}

const GRADE = { 2: 'Complete answer (grade 2)', 1: 'Partial evidence (grade 1)' } as Record<number, string>

// Full page with the annotators' evidence boxes drawn over it, beside the extracted text.
export function PageViewer({ pageId, judged, onClose }: Props) {
  const [page, setPage] = useState<Page | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setPage(null)
    api.page(pageId).then(setPage, (e) => setError(String(e)))
  }, [pageId])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div className="overlay" onClick={onClose}>
      <div className="viewer" role="dialog" aria-modal="true" aria-label={`Page ${pageId}`} onClick={(e) => e.stopPropagation()}>
        <header>
          <div>
            <h2>Page {pageId}</h2>
            <p className={`small ${judged ? 'ok-text' : 'muted'}`}>
              {judged ? GRADE[judged.grade] : 'Not judged relevant for this question'}
            </p>
          </div>
          <button onClick={onClose} aria-label="Close">
            ✕
          </button>
        </header>
        {error && <p className="error">{error}</p>}
        {page && (
          <div className="viewer-body">
            <figure>
              <svg viewBox={`0 0 ${page.width} ${page.height}`} role="img" aria-label="Page image with evidence regions">
                <image href={page.image} width={page.width} height={page.height} />
                {judged?.boxes.map(([x1, y1, x2, y2], i) => (
                  <rect key={i} x={x1} y={y1} width={x2 - x1} height={y2 - y1} className="box" />
                ))}
              </svg>
              <figcaption className="small muted">
                {judged?.boxes.length ? `${judged.boxes.length} annotated evidence region(s) outlined. ` : ''}
                {page.doc_id} · PDF page {page.pdf_page} · {page.license || 'license not specified'} ·{' '}
                <a href={page.url} target="_blank" rel="noreferrer">
                  source document
                </a>
              </figcaption>
            </figure>
            <div className="text">
              <h3 className="small">Extracted text (what text retrievers see)</h3>
              <pre>{page.markdown || '[No extracted text]'}</pre>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
