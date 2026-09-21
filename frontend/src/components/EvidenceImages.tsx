import { useState } from 'react'

interface ImageDisplayProps {
  src: string
  alt: string
  title: string
  className?: string
}

function ImageDisplay({ src, alt, title, className = "w-full h-40" }: ImageDisplayProps) {
  const [isLoading, setIsLoading] = useState(true)
  const [hasError, setHasError] = useState(false)
  const [showModal, setShowModal] = useState(false)

  const handleImageLoad = () => {
    setIsLoading(false)
    setHasError(false)
  }

  const handleImageError = () => {
    setIsLoading(false)
    setHasError(true)
  }

  return (
    <>
      <div className="space-y-2">
        <h4 className="text-sm font-medium text-foreground">{title}</h4>
        <div className={`relative ${className} bg-muted rounded border overflow-hidden`}>
          {/* Loading State */}
          {isLoading && (
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-accent"></div>
            </div>
          )}

          {/* Error State */}
          {hasError && (
            <div className="absolute inset-0 flex flex-col items-center justify-center text-muted-foreground">
              <div className="text-2xl mb-2">📷</div>
              <div className="text-xs text-center px-2">
                Image not available
              </div>
            </div>
          )}

          {/* Image */}
          <img
            src={src}
            alt={alt}
            className={`w-full h-full object-cover cursor-pointer transition-opacity ${
              isLoading || hasError ? 'opacity-0' : 'opacity-100 hover:opacity-90'
            }`}
            onLoad={handleImageLoad}
            onError={handleImageError}
            onClick={() => !hasError && setShowModal(true)}
          />

          {/* Zoom Button Overlay */}
          {!isLoading && !hasError && (
            <button
              onClick={() => setShowModal(true)}
              className="absolute top-2 right-2 p-1 bg-black/50 text-white rounded hover:bg-black/70 transition-colors text-xs"
              title="Click to enlarge"
            >
              🔍
            </button>
          )}
        </div>
      </div>

      {/* Full Screen Modal */}
      {showModal && !hasError && (
        <div className="fixed inset-0 z-50 bg-black/90 flex items-center justify-center p-4" onClick={() => setShowModal(false)}>
          <div className="relative max-w-full max-h-full" onClick={e => e.stopPropagation()}>
            <button
              onClick={() => setShowModal(false)}
              className="absolute -top-10 right-0 text-white hover:text-gray-300 text-lg"
            >
              ✕
            </button>
            <img
              src={src}
              alt={alt}
              className="max-w-full max-h-full object-contain rounded"
            />
            <div className="absolute -bottom-10 left-0 text-white text-sm">
              {title}
            </div>
          </div>
        </div>
      )}
    </>
  )
}

interface EvidenceImagesProps {
  verificationId: string
}

export function EvidenceImages({ verificationId }: EvidenceImagesProps) {
  return (
    <div className="mb-6">
      <h3 className="text-lg font-semibold text-foreground mb-4">Evidence Images</h3>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <ImageDisplay
          src={`/api/images/${verificationId}/document`}
          alt="Document front"
          title="Document Front"
        />
        <ImageDisplay
          src={`/api/images/${verificationId}/document-back`}
          alt="Document back"
          title="Document Back"
        />
        <ImageDisplay
          src={`/api/images/${verificationId}/selfie`}
          alt="Live selfie"
          title="Live Photo"
        />
      </div>
      <div className="mt-2 text-xs text-muted-foreground">
        Click on any image to view full size. Images may not be available if not uploaded during screening.
      </div>
    </div>
  )
}