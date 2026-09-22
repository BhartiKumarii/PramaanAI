import { useEffect, useRef, useState } from 'react'
import { baseURL } from '../api/client'

function getToken(): string {
  return localStorage.getItem('bsa_access_token') ?? ''
}

interface AuthImageProps {
  url: string
  alt: string
  title: string
  timestamp?: string
  type?: string
}

function AuthImage({ url, alt, title, timestamp, type }: AuthImageProps) {
  const [blobUrl, setBlobUrl] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [hasError, setHasError] = useState(false)
  const [showModal, setShowModal] = useState(false)
  const prevUrl = useRef<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setHasError(false)
    if (prevUrl.current) URL.revokeObjectURL(prevUrl.current)

    fetch(url, { headers: { Authorization: `Bearer ${getToken()}` } })
      .then((r) => {
        if (!r.ok) throw new Error(`${r.status}`)
        return r.blob()
      })
      .then((blob) => {
        if (cancelled) return
        const obj = URL.createObjectURL(blob)
        prevUrl.current = obj
        setBlobUrl(obj)
        setLoading(false)
      })
      .catch(() => {
        if (!cancelled) { setHasError(true); setLoading(false) }
      })

    return () => { cancelled = true }
  }, [url])

  return (
    <>
      <div className="space-y-1.5">
        <div className="flex items-center justify-between">
          <h4 className="text-sm font-semibold text-foreground">{title}</h4>
          {type && <span className="text-xs text-muted-foreground bg-secondary border border-border px-2 py-0.5 rounded">{type}</span>}
        </div>
        <div className="relative w-full h-44 bg-secondary border border-border rounded-lg overflow-hidden">
          {loading && (
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-accent" />
            </div>
          )}
          {hasError && (
            <div className="absolute inset-0 flex flex-col items-center justify-center text-muted-foreground gap-2">
              <span className="text-3xl">📷</span>
              <span className="text-xs">Not available</span>
            </div>
          )}
          {blobUrl && (
            <>
              <img
                src={blobUrl}
                alt={alt}
                className="w-full h-full object-contain cursor-pointer hover:opacity-90 transition-opacity"
                onClick={() => setShowModal(true)}
              />
              <button
                onClick={() => setShowModal(true)}
                className="absolute top-2 right-2 bg-black/60 text-white rounded px-2 py-1 text-xs hover:bg-black/80 transition-colors"
              >
                Enlarge
              </button>
            </>
          )}
        </div>
        {timestamp && (
          <p className="text-xs text-muted-foreground">
            Captured: {new Date(timestamp).toLocaleString()}
          </p>
        )}
      </div>

      {showModal && blobUrl && (
        <div
          className="fixed inset-0 z-50 bg-black/90 flex items-center justify-center p-6"
          onClick={() => setShowModal(false)}
        >
          <div className="relative max-w-4xl max-h-full" onClick={(e) => e.stopPropagation()}>
            <button
              onClick={() => setShowModal(false)}
              className="absolute -top-10 right-0 text-white text-lg hover:text-gray-300"
            >
              ✕ Close
            </button>
            <img src={blobUrl} alt={alt} className="max-w-full max-h-[80vh] object-contain rounded-lg shadow-2xl" />
            <p className="mt-3 text-center text-white/70 text-sm">{title}</p>
          </div>
        </div>
      )}
    </>
  )
}

interface EvidenceImagesProps {
  verificationId: string
  caseCreatedAt?: string
}

export function EvidenceImages({ verificationId, caseCreatedAt }: EvidenceImagesProps) {
  const base = `${baseURL}/images/${verificationId}`
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-base font-semibold text-foreground">Evidence Images</h3>
        <div className="text-xs text-muted-foreground space-x-3">
          <span>Source: On-device capture</span>
          {caseCreatedAt && <span>·</span>}
          {caseCreatedAt && <span>Case opened: {new Date(caseCreatedAt).toLocaleDateString()}</span>}
        </div>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <AuthImage url={`${base}/document`}      alt="Document front" title="Document — Front" type="Primary ID" timestamp={caseCreatedAt} />
        <AuthImage url={`${base}/document-back`} alt="Document back"  title="Document — Back"  type="Reverse"    timestamp={caseCreatedAt} />
        <AuthImage url={`${base}/selfie`}         alt="Live photo"    title="Live Photo"        type="Biometric"  timestamp={caseCreatedAt} />
      </div>
      <p className="text-xs text-muted-foreground">
        Images are stored encrypted on the server and accessible only to authorised reviewers.
        Click any image to view full size.
      </p>
    </div>
  )
}
