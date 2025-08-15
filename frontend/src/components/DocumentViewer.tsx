import React, { useEffect, useRef, useState } from 'react'
import OpenSeadragon from 'openseadragon'
import {
  ZoomIn,
  ZoomOut,
  RotateCw,
  Home,
  Maximize,
  MessageSquare,
  Edit3,
  Download
} from 'lucide-react'
import { clsx } from 'clsx'

interface DocumentViewerProps {
  documentId: number
  pageNumber?: number
  onPageChange?: (page: number) => void
  totalPages?: number
  className?: string
}

export default function DocumentViewer({
  documentId,
  pageNumber = 0,
  onPageChange,
  totalPages = 1,
  className
}: DocumentViewerProps) {
  const viewerRef = useRef<HTMLDivElement>(null)
  const [viewer, setViewer] = useState<OpenSeadragon.Viewer | null>(null)
  const [isFullscreen, setIsFullscreen] = useState(false)
  const [showAnnotations, setShowAnnotations] = useState(true)
  const [showRedactions, setShowRedactions] = useState(true)

  useEffect(() => {
    if (!viewerRef.current) return

    // Initialize OpenSeadragon viewer
    const osdViewer = OpenSeadragon({
      element: viewerRef.current,
      prefixUrl: '/openseadragon-images/',
      tileSources: {
        type: 'image',
        url: `/api/documents/${documentId}/thumbnail/${pageNumber}`,
        width: 800,
        height: 1000,
        buildPyramid: false,
      },
      showNavigationControl: false,
      showZoomControl: false,
      showHomeControl: false,
      showFullPageControl: false,
      showRotationControl: false,
      gestureSettingsMouse: {
        scrollToZoom: true,
        clickToZoom: false,
        dblClickToZoom: true,
        pinchToZoom: true,
        flickEnabled: true,
        flickMinSpeed: 120,
        flickMomentum: 0.25,
      },
      zoomPerClick: 2,
      zoomPerScroll: 1.2,
      animationTime: 0.3,
      blendTime: 0.1,
      constrainDuringPan: true,
      wrapHorizontal: false,
      wrapVertical: false,
      visibilityRatio: 0.1,
      minZoomLevel: 0.1,
      maxZoomLevel: 10,
      defaultZoomLevel: 0.8,
    })

    // Add overlay for annotations and redactions
    osdViewer.addHandler('open', () => {
      // Add annotation overlays here
      if (showAnnotations) {
        // TODO: Load and display annotations
      }

      if (showRedactions) {
        // TODO: Load and display redaction shapes
      }
    })

    setViewer(osdViewer)

    return () => {
      if (osdViewer) {
        osdViewer.destroy()
      }
    }
  }, [documentId, pageNumber, showAnnotations, showRedactions])

  const handleZoomIn = () => {
    if (viewer) {
      const currentZoom = viewer.viewport.getZoom()
      viewer.viewport.zoomTo(currentZoom * 1.5)
    }
  }

  const handleZoomOut = () => {
    if (viewer) {
      const currentZoom = viewer.viewport.getZoom()
      viewer.viewport.zoomTo(currentZoom / 1.5)
    }
  }

  const handleZoomHome = () => {
    if (viewer) {
      viewer.viewport.goHome()
    }
  }

  const handleRotate = () => {
    if (viewer) {
      const currentRotation = viewer.viewport.getRotation()
      viewer.viewport.setRotation(currentRotation + 90)
    }
  }

  const handleFullscreen = () => {
    if (viewer) {
      if (isFullscreen) {
        viewer.setFullScreen(false)
      } else {
        viewer.setFullScreen(true)
      }
      setIsFullscreen(!isFullscreen)
    }
  }

  const handlePrevPage = () => {
    if (pageNumber > 0 && onPageChange) {
      onPageChange(pageNumber - 1)
    }
  }

  const handleNextPage = () => {
    if (pageNumber < totalPages - 1 && onPageChange) {
      onPageChange(pageNumber + 1)
    }
  }

  return (
    <div className={clsx('relative bg-gray-100 rounded-lg overflow-hidden', className)}>
      {/* Viewer Container */}
      <div ref={viewerRef} className="w-full h-full min-h-[600px]" />

      {/* Toolbar */}
      <div className="absolute top-4 left-4 bg-white rounded-lg shadow-lg p-2 flex items-center space-x-2">
        <button
          onClick={handleZoomIn}
          className="p-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded transition-colors"
          title="Zoom In"
        >
          <ZoomIn className="h-4 w-4" />
        </button>
        <button
          onClick={handleZoomOut}
          className="p-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded transition-colors"
          title="Zoom Out"
        >
          <ZoomOut className="h-4 w-4" />
        </button>
        <button
          onClick={handleZoomHome}
          className="p-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded transition-colors"
          title="Fit to Screen"
        >
          <Home className="h-4 w-4" />
        </button>
        <button
          onClick={handleRotate}
          className="p-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded transition-colors"
          title="Rotate"
        >
          <RotateCw className="h-4 w-4" />
        </button>
        <button
          onClick={handleFullscreen}
          className="p-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded transition-colors"
          title="Fullscreen"
        >
          <Maximize className="h-4 w-4" />
        </button>
      </div>

      {/* Page Navigation */}
      {totalPages > 1 && (
        <div className="absolute bottom-4 left-1/2 transform -translate-x-1/2 bg-white rounded-lg shadow-lg p-2 flex items-center space-x-2">
          <button
            onClick={handlePrevPage}
            disabled={pageNumber === 0}
            className="px-3 py-1 text-sm text-gray-600 hover:text-gray-900 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Previous
          </button>
          <span className="text-sm text-gray-600 px-2">
            {pageNumber + 1} of {totalPages}
          </span>
          <button
            onClick={handleNextPage}
            disabled={pageNumber === totalPages - 1}
            className="px-3 py-1 text-sm text-gray-600 hover:text-gray-900 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Next
          </button>
        </div>
      )}

      {/* Annotation Tools */}
      <div className="absolute top-4 right-4 bg-white rounded-lg shadow-lg p-2 flex flex-col space-y-2">
        <button
          onClick={() => setShowAnnotations(!showAnnotations)}
          className={clsx(
            'p-2 rounded transition-colors',
            showAnnotations
              ? 'text-primary-600 bg-primary-50'
              : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
          )}
          title="Toggle Annotations"
        >
          <MessageSquare className="h-4 w-4" />
        </button>
        <button
          onClick={() => setShowRedactions(!showRedactions)}
          className={clsx(
            'p-2 rounded transition-colors',
            showRedactions
              ? 'text-red-600 bg-red-50'
              : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
          )}
          title="Toggle Redactions"
        >
          <Edit3 className="h-4 w-4" />
        </button>
        <button
          className="p-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded transition-colors"
          title="Download Page"
        >
          <Download className="h-4 w-4" />
        </button>
      </div>
    </div>
  )
}
