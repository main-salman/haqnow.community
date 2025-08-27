import React, { useEffect, useRef, useState, useCallback } from 'react'
import { logEvent, logError, logWarn } from '../utils/log'
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

// Image Fallback Viewer Component
function ImageFallbackViewer({
  documentId,
  pageNumber,
  commentMode,
  redactionMode,
  onAddCommentAt,
  onRedactionCreate,
  onRedactionUpdate,
  onRedactionDelete,
  comments,
  redactions
}: {
  documentId: number
  pageNumber: number
  commentMode: boolean
  redactionMode: boolean
  onAddCommentAt?: (x: number, y: number, page: number) => void
  onRedactionCreate?: (redaction: any) => void
  onRedactionUpdate?: (redaction: { id: number; page_number: number; x_start: number; y_start: number; x_end: number; y_end: number }) => void
  onRedactionDelete?: (redactionId: number) => void
  comments: any[]
  redactions: any[]
}) {
  const [showCommentInput, setShowCommentInput] = useState(false)
  const [commentPosition, setCommentPosition] = useState({ x: 0, y: 0 })
  const [commentText, setCommentText] = useState('')
  const [isDrawingRedaction, setIsDrawingRedaction] = useState(false)
  const [redactionStart, setRedactionStart] = useState<{x: number, y: number} | null>(null)
  const [currentRedaction, setCurrentRedaction] = useState<HTMLDivElement | null>(null)
  const [imageSize, setImageSize] = useState({ width: 0, height: 0 })
  const imgRef = useRef<HTMLImageElement>(null)
  const resizingRef = useRef<{ id: number; startX: number; startY: number; orig: { x: number; y: number; w: number; h: number } } | null>(null)

  // Debug logging
  console.log('🔍 ImageFallbackViewer render:', {
    documentId,
    pageNumber,
    commentMode,
    redactionMode,
    commentsCount: comments.length,
    redactionsCount: redactions.length,
    imageSize
  })

  return (
    <div className="relative w-full h-full min-h-[600px] bg-white">
      <img
        ref={imgRef}
        src={`/api/documents/${documentId}/pages/${pageNumber}`}
        alt={`Document ${documentId} page ${pageNumber + 1}`}
        className="w-full h-auto object-contain"
        onLoad={(e) => {
          const img = e.currentTarget
          setImageSize({ width: img.offsetWidth, height: img.offsetHeight })
        }}
                onClick={(e) => {
          // Prevent click if we're in redaction mode (use drag instead)
          if (redactionMode) {
            e.preventDefault()
            return
          }

          if (commentMode && onAddCommentAt) {
            const rect = e.currentTarget.getBoundingClientRect()
            const x = e.clientX - rect.left
            const y = e.clientY - rect.top

            // Show in-place comment input
            setCommentPosition({ x, y })
            setShowCommentInput(true)
            setCommentText('')
          }
        }}
                        onMouseDown={(e) => {
          if (redactionMode && onRedactionCreate) {
            e.preventDefault()
            e.stopPropagation()

            const rect = e.currentTarget.getBoundingClientRect()
            const startX = e.clientX - rect.left
            const startY = e.clientY - rect.top

            console.log('🎯 REDACTION: Starting draw at', startX, startY, 'redactionMode:', redactionMode)

            setRedactionStart({ x: startX, y: startY })
            setIsDrawingRedaction(true)

            // Create visual redaction rectangle
            const redactionDiv = document.createElement('div')
            redactionDiv.style.position = 'absolute'
            redactionDiv.style.backgroundColor = 'rgba(255, 0, 0, 0.6)' // Red while drawing
            redactionDiv.style.border = '2px solid red'
            redactionDiv.style.pointerEvents = 'none'
            redactionDiv.style.zIndex = '1000'
            redactionDiv.style.left = startX + 'px'
            redactionDiv.style.top = startY + 'px'
            redactionDiv.style.width = '2px'
            redactionDiv.style.height = '2px'
            redactionDiv.id = 'temp-redaction-' + Date.now()

            e.currentTarget.parentElement?.appendChild(redactionDiv)
            setCurrentRedaction(redactionDiv)

            // Use global mouse events for reliable dragging
                        const handleGlobalMouseMove = (moveEvent: MouseEvent) => {
              if (redactionDiv) {
                const currentX = moveEvent.clientX - rect.left
                const currentY = moveEvent.clientY - rect.top

                const left = Math.min(startX, currentX)
                const top = Math.min(startY, currentY)
                const width = Math.abs(currentX - startX)
                const height = Math.abs(currentY - startY)

                redactionDiv.style.left = left + 'px'
                redactionDiv.style.top = top + 'px'
                redactionDiv.style.width = Math.max(2, width) + 'px'
                redactionDiv.style.height = Math.max(2, height) + 'px'

                console.log('🎯 REDACTION: Drawing', { left, top, width, height })
              }
            }

            const handleGlobalMouseUp = (upEvent: MouseEvent) => {
              if (redactionDiv && onRedactionCreate) {
                const endX = upEvent.clientX - rect.left
                const endY = upEvent.clientY - rect.top

                // Convert to image coordinates (300 DPI)
                const imgX1 = (Math.min(startX, endX) / rect.width) * 2400
                const imgY1 = (Math.min(startY, endY) / rect.height) * 3600
                const imgX2 = (Math.max(startX, endX) / rect.width) * 2400
                const imgY2 = (Math.max(startY, endY) / rect.height) * 3600

                if (Math.abs(imgX2 - imgX1) > 10 && Math.abs(imgY2 - imgY1) > 10) {
                  onRedactionCreate({
                    page_number: pageNumber,
                    x_start: imgX1,
                    y_start: imgY1,
                    x_end: imgX2,
                    y_end: imgY2,
                    reason: 'User redaction'
                  })
                }

                redactionDiv.remove()
                setCurrentRedaction(null)
                setIsDrawingRedaction(false)
                setRedactionStart(null)
              }

              document.removeEventListener('mousemove', handleGlobalMouseMove)
              document.removeEventListener('mouseup', handleGlobalMouseUp)
            }

            document.addEventListener('mousemove', handleGlobalMouseMove)
            document.addEventListener('mouseup', handleGlobalMouseUp)
          }
        }}
        style={{ cursor: commentMode ? 'crosshair' : redactionMode ? 'crosshair' : 'default' }}
      />

                  {/* Comment pins on image fallback */}
      {imageSize.width > 0 && comments
        .filter(c => c.page_number === pageNumber)
        .map((comment) => {
          // Use relative positioning based on image dimensions
          const x = Math.max(0, Math.min((comment.x_position / 2400) * imageSize.width, imageSize.width - 12))
          const y = Math.max(0, Math.min((comment.y_position / 3600) * imageSize.height, imageSize.height - 12))

          return (
            <div
              key={comment.id}
              className="absolute w-3 h-3 bg-blue-600 rounded-full shadow-lg cursor-pointer z-20"
              style={{
                left: x,
                top: y,
                transform: 'translate(-50%, -50%)' // Center the pin on the coordinates
              }}
              title={comment.content}
              onClick={(e) => {
                e.stopPropagation()
                alert(comment.content)
              }}
            />
          )
        })}

                  {/* Redaction rectangles on image fallback */}
      {imageSize.width > 0 && redactions
        .filter(r => r.page_number === pageNumber)
        .map((redaction) => {
          const x = (Math.min(redaction.x_start, redaction.x_end) / 2400) * imageSize.width
          const y = (Math.min(redaction.y_start, redaction.y_end) / 3600) * imageSize.height
          const width = (Math.abs(redaction.x_end - redaction.x_start) / 2400) * imageSize.width
          const height = (Math.abs(redaction.y_end - redaction.y_start) / 3600) * imageSize.height

          return (
            <div
              key={redaction.id}
              className="absolute bg-black bg-opacity-90 border border-red-500 z-15 cursor-move"
              style={{ left: x, top: y, width, height }}
              title={`Redaction: ${redaction.reason || 'No reason'}`}
              data-testid="redaction-overlay"
            >
              <button
                type="button"
                data-testid="redaction-delete"
                onClick={(e) => {
                  e.stopPropagation()
                  if (redaction.id && onRedactionDelete) {
                    if (confirm('Delete this redaction?')) onRedactionDelete(redaction.id)
                  }
                }}
                style={{
                  position: 'absolute',
                  right: -2,
                  top: -2,
                  width: 20,
                  height: 20,
                  background: '#ef4444',
                  color: 'white',
                  border: '2px solid white',
                  borderRadius: '50%',
                  cursor: 'pointer',
                  zIndex: 10003,
                  lineHeight: 1,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
                title="Delete redaction"
              >
                ×
              </button>

              <div
                data-testid="redaction-resize-handle"
                onMouseDown={(e) => {
                  e.stopPropagation()
                  const parent = e.currentTarget.parentElement as HTMLDivElement
                  const rect = parent.getBoundingClientRect()
                  resizingRef.current = {
                    id: redaction.id!,
                    startX: e.clientX,
                    startY: e.clientY,
                    orig: { x: rect.left, y: rect.top, w: rect.width, h: rect.height }
                  }
                  const handleMove = (me: MouseEvent) => {
                    if (!resizingRef.current) return
                    const dx = me.clientX - resizingRef.current.startX
                    const dy = me.clientY - resizingRef.current.startY
                    parent.style.width = Math.max(2, resizingRef.current.orig.w + dx) + 'px'
                    parent.style.height = Math.max(2, resizingRef.current.orig.h + dy) + 'px'
                  }
                  const handleUp = () => {
                    const data = resizingRef.current
                    resizingRef.current = null
                    document.removeEventListener('mousemove', handleMove)
                    document.removeEventListener('mouseup', handleUp)
                    if (!data || !onRedactionUpdate) return
                    const img = imgRef.current!
                    const imgRect = img.getBoundingClientRect()
                    const parentRect = parent.getBoundingClientRect()
                    const imgX1 = ((parentRect.left - imgRect.left) / imgRect.width) * 2400
                    const imgY1 = ((parentRect.top - imgRect.top) / imgRect.height) * 3600
                    const imgX2 = ((parentRect.right - imgRect.left) / imgRect.width) * 2400
                    const imgY2 = ((parentRect.bottom - imgRect.top) / imgRect.height) * 3600
                    onRedactionUpdate({ id: redaction.id!, page_number: pageNumber, x_start: imgX1, y_start: imgY1, x_end: imgX2, y_end: imgY2 })
                  }
                  document.addEventListener('mousemove', handleMove)
                  document.addEventListener('mouseup', handleUp)
                }}
                style={{
                  position: 'absolute',
                  width: 10,
                  height: 10,
                  right: 0,
                  bottom: 0,
                  background: '#ffffff',
                  border: '1px solid #000000',
                  cursor: 'nwse-resize',
                  zIndex: 10002,
                }}
              />
            </div>
          )
        })}

      {/* In-place comment input */}
      {showCommentInput && (
        <div
          className="absolute z-50 bg-white border border-gray-300 rounded-lg shadow-lg p-3"
          style={{
            left: commentPosition.x,
            top: commentPosition.y - 80,
            minWidth: '200px'
          }}
        >
          <textarea
            value={commentText}
            onChange={(e) => setCommentText(e.target.value)}
            placeholder="Enter your comment..."
            className="w-full p-2 border border-gray-200 rounded text-sm resize-none"
            rows={3}
            autoFocus
          />
          <div className="flex justify-end space-x-2 mt-2">
            <button
              onClick={() => {
                setShowCommentInput(false)
                setCommentText('')
              }}
              className="px-3 py-1 text-sm text-gray-600 hover:text-gray-800"
            >
              Cancel
            </button>
            <button
              onClick={() => {
                if (commentText.trim() && onAddCommentAt) {
                  const img = document.querySelector(`img[src*="/api/documents/${documentId}/pages/${pageNumber}"]`) as HTMLImageElement
                  if (img) {
                    const rect = img.getBoundingClientRect()
                    const imgX = (commentPosition.x / rect.width) * 2400
                    const imgY = (commentPosition.y / rect.height) * 3600

                    // Create a custom comment handler that includes the text
                    window.tempCommentText = commentText.trim()
                    onAddCommentAt(imgX, imgY, pageNumber)
                  }
                }
                setShowCommentInput(false)
                setCommentText('')
              }}
              className="px-3 py-1 text-sm bg-blue-600 text-white rounded hover:bg-blue-700"
            >
              Add
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

interface DocumentViewerProps {
  documentId: number
  pageNumber?: number
  onPageChange?: (page: number) => void
  totalPages?: number
  className?: string
  redactionMode?: boolean
  commentMode?: boolean
  onRedactionCreate?: (redaction: {
    page_number: number
    x_start: number
    y_start: number
    x_end: number
    y_end: number
    reason?: string
  }) => void
  onRedactionUpdate?: (redaction: {
    id: number
    page_number: number
    x_start: number
    y_start: number
    x_end: number
    y_end: number
    reason?: string
  }) => void
  onRedactionDelete?: (redactionId: number) => void
  onAddCommentAt?: (x: number, y: number, page: number) => void
  redactions?: Array<{
    id?: number
    page_number: number
    x_start: number
    y_start: number
    x_end: number
    y_end: number
  }>
  comments?: Array<{
    id?: number
    page_number: number
    x_position: number
    y_position: number
    content?: string
  }>
  showAnnotations?: boolean
  showRedactions?: boolean
}

export default function DocumentViewer({
  documentId,
  pageNumber = 0,
  onPageChange,
  totalPages = 1,
  className,
  redactionMode = false,
  commentMode = false,
  onRedactionCreate,
  onRedactionUpdate,
  onRedactionDelete,
  onAddCommentAt,
  redactions = [],
  comments = [],
  showAnnotations: propShowAnnotations,
  showRedactions: propShowRedactions,
}: DocumentViewerProps) {
  const viewerRef = useRef<HTMLDivElement>(null)
  const [viewer, setViewer] = useState<OpenSeadragon.Viewer | null>(null)
  const [useImageFallback, setUseImageFallback] = useState(false)

  // Debug logging
  // Reduced logging - only log when data changes
  if (comments.length > 0 || redactions.length > 0) {
    console.log('📊 Data loaded:', { comments: comments.length, redactions: redactions.length, mode: commentMode ? 'comment' : redactionMode ? 'redact' : 'view' })
  }
  const [isFullscreen, setIsFullscreen] = useState(false)
  // Use props if provided, otherwise default to internal state
  const [internalShowAnnotations, setInternalShowAnnotations] = useState(true)
  const [internalShowRedactions, setInternalShowRedactions] = useState(true)
  const refreshTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const showAnnotations = propShowAnnotations !== undefined ? propShowAnnotations : internalShowAnnotations
  const showRedactions = propShowRedactions !== undefined ? propShowRedactions : internalShowRedactions
  const [showCommentModal, setShowCommentModal] = useState(false)
  const [selectedComment, setSelectedComment] = useState<any>(null)
  const [commentModalPosition, setCommentModalPosition] = useState({ x: 0, y: 0 })
  // HTML5 inline input for comments in OSD viewer
  const [showOsdCommentInput, setShowOsdCommentInput] = useState(false)
  const [osdCommentPos, setOsdCommentPos] = useState<{ x: number; y: number }>({ x: 0, y: 0 })
  const [osdCommentText, setOsdCommentText] = useState('')
  const osdPendingCommentRef = useRef<{ x: number; y: number; page: number } | null>(null)

  // Debounced overlay refresh to improve performance
  const debouncedRefreshOverlays = useCallback(() => {
    if (refreshTimeoutRef.current) {
      clearTimeout(refreshTimeoutRef.current)
    }
    refreshTimeoutRef.current = setTimeout(() => {
      if (viewer) {
        refreshOverlays()
      }
    }, 100) // 100ms debounce
  }, [viewer])

  // Function to show existing comment popup
  const showCommentPopup = useCallback((comment: any, position: any) => {
    setSelectedComment(comment)
    setCommentModalPosition({ x: position.x, y: position.y })
    setShowCommentModal(true)
  }, [])
  const isDrawingRef = useRef(false)
  const drawStartRef = useRef<{x: number, y: number} | null>(null)
  const currentRedactionRef = useRef<HTMLDivElement | null>(null)
  const overlaysRef = useRef<{ type: 'redaction' | 'comment'; el: HTMLElement }[]>([])
  const draggingRef = useRef<{ id: number; startX: number; startY: number; orig: { x1: number; y1: number; x2: number; y2: number } } | null>(null)
  const resizingRef = useRef<{ id: number; startX: number; startY: number; orig: { x1: number; y1: number; x2: number; y2: number } } | null>(null)
  // Suppress viewer canvas interactions while manipulating overlays to avoid creating new shapes
  const suppressCanvasInteractionsRef = useRef(false)
  // Track live overlay element and last proposed image-rect during drag/resize for single API update on mouseup
  const activeOverlayElRef = useRef<HTMLElement | null>(null)
  const pendingUpdateRef = useRef<{ id: number; x1: number; y1: number; x2: number; y2: number } | null>(null)

  useEffect(() => {
    if (!viewerRef.current) return

    // Initialize OpenSeadragon viewer with single 300 DPI image per page
    const osdViewer = OpenSeadragon({
      element: viewerRef.current,
      prefixUrl: '/openseadragon-images/',
      tileSources: {
        type: 'image',
        url: `/api/documents/${documentId}/pages/${pageNumber}`,
        width: 2550,
        height: 3300,
        buildPyramid: false
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
      maxZoomLevel: 20,
      defaultZoomLevel: 1.0,
    })

    // Add error handling for tile loading
    osdViewer.addHandler('open-failed', (event: any) => {
      console.error('🔴 OSD open failed:', event)
      setUseImageFallback(true)
    })

    osdViewer.addHandler('tile-load-failed', (event: any) => {
      console.error('🔴 OSD tile load failed:', event)
    })

    osdViewer.addHandler('open', () => {
      console.log('✅ OSD opened successfully')
      window.clearTimeout(fallbackTimer)
      setUseImageFallback(false)
    })

    // If OSD fails to open quickly, fall back to simple <img>
    const fallbackTimer = window.setTimeout(() => {
      try {
        const count = osdViewer.world.getItemCount()
        console.log(`🔍 OSD fallback check: ${count} items loaded`)
        if (count === 0) {
          console.log('⚠️ OSD failed to load, using image fallback')
          setUseImageFallback(true)
        }
      } catch (e) {
        console.error('🔴 OSD fallback check error:', e)
        setUseImageFallback(true)
      }
    }, 3000)

    // Handle single clicks to add comments (when in comment mode)
    osdViewer.addHandler('canvas-click', (event: any) => {
      if (suppressCanvasInteractionsRef.current) {
        logWarn('Viewer', 'canvas-click suppressed due to overlay interaction')
        return
      }
      logEvent('Viewer', 'canvas-click', { commentMode, redactionMode })
      if (redactionMode) return
      if (!commentMode) return

      // If clicking directly on a comment pin, don't open inline input
      const targetEl = event.originalEvent?.target as HTMLElement | undefined
      if (targetEl && (targetEl.getAttribute('data-testid') === 'comment-pin' || targetEl.closest('[data-testid="comment-pin"]'))) {
        return
      }

      const item = osdViewer.world.getItemAt(0)
      if (!item) return
      const vpPoint = osdViewer.viewport.pointFromPixel(event.position)
      const imgPoint = item.viewportToImageCoordinates(vpPoint)
      // Screen-relative position for inline popup
      const viewerRect = (viewerRef.current as HTMLDivElement).getBoundingClientRect()
      const screenX = event.originalEvent.clientX - viewerRect.left
      const screenY = event.originalEvent.clientY - viewerRect.top

      // Check if we clicked near an existing comment (within 50 pixels)
      const clickRadius = 120
      const nearbyComment = comments.find(c => {
        if (c.page_number !== pageNumber) return false
        const distance = Math.sqrt(
          Math.pow(c.x_position - imgPoint.x, 2) +
          Math.pow(c.y_position - imgPoint.y, 2)
        )
        return distance <= clickRadius
      })

      if (nearbyComment) {
        logEvent('Comments', 'Clicked near existing comment', { id: nearbyComment.id, x: nearbyComment.x_position, y: nearbyComment.y_position })
        // Show existing comment in a popup
        showCommentPopup(nearbyComment, event.position)
      } else {
        // Open inline HTML5 input near the click position
        setOsdCommentPos({ x: screenX, y: screenY })
        setOsdCommentText('')
        setShowOsdCommentInput(true)
        osdPendingCommentRef.current = { x: imgPoint.x, y: imgPoint.y, page: pageNumber }
        logEvent('Comments', 'OSD inline input opened', { imgX: imgPoint.x, imgY: imgPoint.y, page: pageNumber })
      }
    })

    // Guard redaction drawing press when suppression is active
    osdViewer.addHandler('canvas-press', () => {
      if (suppressCanvasInteractionsRef.current) {
        logWarn('Viewer', 'canvas-press suppressed due to overlay interaction')
        return
      }
    })
    // Always clear suppression on release
    osdViewer.addHandler('canvas-release', () => {
      if (suppressCanvasInteractionsRef.current) {
        suppressCanvasInteractionsRef.current = false
        try { if (viewer && (viewer as any).setMouseNavEnabled && (viewer as any).tracker) { (viewer as any).setMouseNavEnabled(true) } } catch {}
        logEvent('Viewer', 'canvas-release: suppression cleared', {})
      }
    })

    // Add overlay for annotations and redactions when image opens
    osdViewer.addHandler('open', () => {
      window.clearTimeout(fallbackTimer)
      setUseImageFallback(false)
    })

    // Wait for tile to be fully loaded before rendering overlays
    osdViewer.addHandler('tile-loaded', () => {
      console.log('🔍 OSD: Tile loaded, triggering overlay refresh')
      // Small delay to ensure item is ready
      setTimeout(() => {
        setViewer(prev => prev) // Force overlay effect re-run
      }, 50)
    })

    // Utility: hit-test helper for redactions in IMAGE space
    const hitTestRedaction = (imgX: number, imgY: number) => {
      const currentPageReds = redactions.filter(r => r.page_number === pageNumber)
      for (const r of currentPageReds) {
        const x1 = Math.min(r.x_start, r.x_end)
        const y1 = Math.min(r.y_start, r.y_end)
        const x2 = Math.max(r.x_start, r.x_end)
        const y2 = Math.max(r.y_start, r.y_end)
        if (imgX >= x1 && imgX <= x2 && imgY >= y1 && imgY <= y2) {
          return { id: (r as any).id as number | undefined, x1, y1, x2, y2 }
        }
      }
      return null
    }

    // Hit-test for delete (top-right 20x20px in image space approx)
    const isInDeleteHotspot = (imgX: number, imgY: number, rect: {x1:number,y1:number,x2:number,y2:number}) => {
      const hotspotSize = 30 // pixels in image space; rough but works across zooms
      return imgX >= rect.x2 - hotspotSize && imgX <= rect.x2 && imgY >= rect.y1 && imgY <= rect.y1 + hotspotSize
    }

    // Hit-test for resize (bottom-right 20x20px)
    const isInResizeHotspot = (imgX: number, imgY: number, rect: {x1:number,y1:number,x2:number,y2:number}) => {
      const hotspotSize = 30
      return imgX >= rect.x2 - hotspotSize && imgX <= rect.x2 && imgY >= rect.y2 - hotspotSize && imgY <= rect.y2
    }

    // Intercept canvas-press to start drag/resize when pressing on existing redaction
    osdViewer.addHandler('canvas-press', (event: any) => {
      if (!redactionMode) return
      const item = osdViewer.world.getItemAt(0)
      if (!item) return
      const vpPoint = osdViewer.viewport.pointFromPixel(event.position)
      const imgPoint = item.viewportToImageCoordinates(vpPoint)
      const hit = hitTestRedaction(imgPoint.x, imgPoint.y)
      if (hit && hit.id) {
        // Prevent drawing, start drag or resize
        isDrawingRef.current = false
        suppressCanvasInteractionsRef.current = true
        try { if (viewer && (viewer as any).setMouseNavEnabled && (viewer as any).tracker) { (viewer as any).setMouseNavEnabled(false) } } catch {}
        const rect = { x1: hit.x1, y1: hit.y1, x2: hit.x2, y2: hit.y2 }
        if (isInResizeHotspot(imgPoint.x, imgPoint.y, rect)) {
          resizingRef.current = { id: hit.id, startX: imgPoint.x, startY: imgPoint.y, orig: rect }
          pendingUpdateRef.current = null
          logEvent('Redactions', 'Start resize (hit-test)', { id: hit.id, imgX: imgPoint.x, imgY: imgPoint.y })
        } else {
          draggingRef.current = { id: hit.id, startX: imgPoint.x, startY: imgPoint.y, orig: rect }
          pendingUpdateRef.current = null
          logEvent('Redactions', 'Start drag (hit-test)', { id: hit.id, imgX: imgPoint.x, imgY: imgPoint.y })
        }
        // Do not proceed with drawing
        return
      }
      // else proceed (drawing handled below)
    })

    // Canvas click for delete hotspot
    osdViewer.addHandler('canvas-click', (event: any) => {
      if (!redactionMode) return
      const item = osdViewer.world.getItemAt(0)
      if (!item) return
      const vpPoint = osdViewer.viewport.pointFromPixel(event.position)
      const imgPoint = item.viewportToImageCoordinates(vpPoint)
      const hit = hitTestRedaction(imgPoint.x, imgPoint.y)
      if (hit && hit.id && isInDeleteHotspot(imgPoint.x, imgPoint.y, hit)) {
        event.originalEvent?.preventDefault?.()
        event.originalEvent?.stopPropagation?.()
        suppressCanvasInteractionsRef.current = true
        logEvent('Redactions', 'Delete clicked (hit-test)', { id: hit.id })
        if (confirm('Delete this redaction?')) onRedactionDelete?.(hit.id)
      }
    })

    // Add redaction drawing handlers
    if (redactionMode) {
      console.log('🔍 OSD: Setting up redaction handlers')
      // Ensure suppression is reset when entering redact mode
      suppressCanvasInteractionsRef.current = false

      // Disable pan/zoom during redaction mode
      osdViewer.panHorizontal = false
      osdViewer.panVertical = false
      osdViewer.zoomPerClick = 1.0
      osdViewer.zoomPerScroll = 1.0

      osdViewer.addHandler('canvas-press', (event: any) => {
        // Respect overlay interaction suppression to avoid spawning new rectangles while resizing/moving
        if (suppressCanvasInteractionsRef.current) {
          logWarn('Viewer', 'canvas-press suppressed due to overlay interaction')
          return
        }
        console.log('🎯 OSD canvas-press: redactionMode=', redactionMode, 'isDrawing=', isDrawingRef.current)
        if (redactionMode && !isDrawingRef.current) {
          const item = osdViewer.world.getItemAt(0)
          if (!item) return

          // Store start position in PIXEL coordinates (not image coordinates)
          const startPixel = event.position
          drawStartRef.current = {x: startPixel.x, y: startPixel.y}
          isDrawingRef.current = true

          // Create visual redaction rectangle
          const redactionDiv = document.createElement('div')
          redactionDiv.style.position = 'absolute'
          redactionDiv.style.backgroundColor = 'rgba(255, 0, 0, 0.6)'
          redactionDiv.style.border = '2px solid red'
          redactionDiv.style.pointerEvents = 'none'
          redactionDiv.style.zIndex = '1000'
          redactionDiv.style.left = startPixel.x + 'px'
          redactionDiv.style.top = startPixel.y + 'px'
          redactionDiv.style.width = '2px'
          redactionDiv.style.height = '2px'

          viewerRef.current?.appendChild(redactionDiv)
          currentRedactionRef.current = redactionDiv
          console.log('🎯 OSD: Created redaction div at pixel', startPixel.x, startPixel.y)
        }
      })

                  osdViewer.addHandler('canvas-drag', (event: any) => {
        if (redactionMode && isDrawingRef.current && drawStartRef.current && currentRedactionRef.current) {
          // Work entirely in pixel coordinates during drag
          const currentPixel = event.position
          const startPixel = drawStartRef.current

          const left = Math.min(startPixel.x, currentPixel.x)
          const top = Math.min(startPixel.y, currentPixel.y)
          const width = Math.abs(currentPixel.x - startPixel.x)
          const height = Math.abs(currentPixel.y - startPixel.y)

          currentRedactionRef.current.style.left = left + 'px'
          currentRedactionRef.current.style.top = top + 'px'
          currentRedactionRef.current.style.width = Math.max(2, width) + 'px'
          currentRedactionRef.current.style.height = Math.max(2, height) + 'px'

          console.log('🎯 OSD: Dragging redaction pixels', { left, top, width, height })
        }
      })

            osdViewer.addHandler('canvas-release', (event: any) => {
        if (redactionMode && isDrawingRef.current && drawStartRef.current && currentRedactionRef.current) {
          const item = osdViewer.world.getItemAt(0)
          if (!item) return

                    // Convert PIXEL coordinates to IMAGE coordinates only at the end
          const startPixel = drawStartRef.current
          const endPixel = event.position

          const startViewport = osdViewer.viewport.pointFromPixel(new OpenSeadragon.Point(startPixel.x, startPixel.y))
          const endViewport = osdViewer.viewport.pointFromPixel(new OpenSeadragon.Point(endPixel.x, endPixel.y))

          const startImage = item.viewportToImageCoordinates(startViewport)
          const endImage = item.viewportToImageCoordinates(endViewport)
          // Clamp to bounds
          let maxW = 3000
          let maxH = 4000
          try {
            const size = (item as any).getContentSize?.()
            if (size && typeof size.x === 'number' && typeof size.y === 'number') { maxW = size.x; maxH = size.y }
          } catch {}

          // Calculate redaction coordinates in IMAGE PIXELS
          let x_start = Math.min(startImage.x, endImage.x)
          let y_start = Math.min(startImage.y, endImage.y)
          let x_end = Math.max(startImage.x, endImage.x)
          let y_end = Math.max(startImage.y, endImage.y)
          x_start = Math.max(0, Math.min(maxW, x_start))
          y_start = Math.max(0, Math.min(maxH, y_start))
          x_end = Math.max(0, Math.min(maxW, x_end))
          y_end = Math.max(0, Math.min(maxH, y_end))

          console.log('🎯 OSD: Final redaction coords:', { x_start, y_start, x_end, y_end, width: x_end - x_start, height: y_end - y_start })

          if (Math.abs(x_end - x_start) > 10 && Math.abs(y_end - y_start) > 10) {
            console.log('🎯 OSD: Creating redaction via API')
            onRedactionCreate?.({
              page_number: pageNumber,
              x_start,
              y_start,
              x_end,
              y_end,
              reason: 'User redaction'
            })
          } else {
            console.log('🎯 OSD: Redaction too small, not creating (min 10px)')
          }

          currentRedactionRef.current.remove()
          currentRedactionRef.current = null
          isDrawingRef.current = false
          drawStartRef.current = null
        }
      })
    } else {
      // Re-enable pan/zoom when not in redaction mode
      osdViewer.panHorizontal = true
      osdViewer.panVertical = true
      osdViewer.zoomPerClick = 2.0
      osdViewer.zoomPerScroll = 1.2
    }

    setViewer(osdViewer)

    // Fallback: if image fails to load, render a simple placeholder to avoid blank page
    osdViewer.addHandler('open-failed', () => {
      if (viewerRef.current) {
        viewerRef.current.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:#666">Unable to load page preview.</div>'
      }
    })

    return () => {
      if (osdViewer) {
        osdViewer.destroy()
      }
      window.clearTimeout(fallbackTimer)
    }
  }, [documentId, pageNumber, showAnnotations, showRedactions, redactionMode, commentMode])

  // Force overlay refresh when switching modes
  useEffect(() => {
    if (!viewer) return
    console.log('🎯 MODE SWITCH:', { redactionMode, commentMode, commentsToShow: comments.length, redactionsToShow: redactions.length })
    // Small delay to ensure mode change is processed
    setTimeout(() => {
      setViewer(prev => prev) // Force overlay effect re-run
    }, 50)
  }, [redactionMode, commentMode, comments.length, redactions.length])

    // Render overlays for redactions and comments
  useEffect(() => {
    if (!viewer) return

    // Clear previous overlays
    overlaysRef.current.forEach(({ el }) => {
      try { viewer.removeOverlay(el) } catch {}
    })
    overlaysRef.current = []

    console.log('🎯 RENDERING OVERLAYS:', { comments: comments.length, redactions: redactions.length, showAnnotations, showRedactions })

        // Check viewer state and wait for tiled image if needed
    const tiledImage = viewer.world.getItemAt(0)
    if (!tiledImage) {
      console.log('⏳ WAITING FOR TILED IMAGE - using fallback rendering')
      // Don't return - continue with fallback rendering without coordinate conversion
    } else {
      console.log('✅ TILED IMAGE READY - rendering overlays with coordinate conversion')
    }

    // Redaction overlays
    if (showRedactions) {
      const pageRedactions = redactions.filter(r => r.page_number === pageNumber)
      console.log('🔲 REDACTION BOXES:', pageRedactions.length, 'boxes on page', pageNumber, 'showRedactions:', showRedactions)
      pageRedactions.forEach((r) => {
          const el = document.createElement('div')
          el.setAttribute('data-testid', 'redaction-overlay')
          el.setAttribute('data-redaction-id', String((r as any).id ?? ''))
          el.className = (el.className ? el.className + ' ' : '') + 'redaction-rectangle'
          el.style.background = 'rgba(0,0,0,0.9)'
          el.style.border = '1px solid rgba(0,0,0,1)'
          el.style.pointerEvents = 'auto'
          el.style.touchAction = 'none'
          el.style.cursor = 'move'
          el.style.position = 'relative'
          el.style.zIndex = '10000'
          const xRaw = Math.min(r.x_start, r.x_end)
          const yRaw = Math.min(r.y_start, r.y_end)
          const wRaw = Math.abs(r.x_end - r.x_start)
          const hRaw = Math.abs(r.y_end - r.y_start)
          ;(el as any).dataset.x1 = String(xRaw)
          ;(el as any).dataset.y1 = String(yRaw)
          ;(el as any).dataset.x2 = String(xRaw + wRaw)
          ;(el as any).dataset.y2 = String(yRaw + hRaw)
          let rect: OpenSeadragon.Rect
          const isPixel = xRaw > 1 || yRaw > 1 || wRaw > 1 || hRaw > 1
          if (isPixel && tiledImage) {
            const imageRect = new OpenSeadragon.Rect(xRaw, yRaw, wRaw, hRaw)
            rect = tiledImage.imageToViewportRectangle(imageRect)
          } else {
            // Fallback: treat coordinates as normalized viewport coordinates
            rect = new OpenSeadragon.Rect(xRaw / 2550, yRaw / 3300, wRaw / 2550, hRaw / 3300)
          }
          try { viewer.addOverlay({ element: el, location: rect }) } catch {}
          overlaysRef.current.push({ type: 'redaction', el })

          // Add resize handle (bottom-right)
          const handle = document.createElement('div')
          handle.setAttribute('data-testid', 'redaction-resize-handle')
          handle.style.position = 'absolute'
          handle.style.width = '10px'
          handle.style.height = '10px'
          handle.style.right = '0'
          handle.style.bottom = '0'
          handle.style.background = '#ffffff'
          handle.style.border = '1px solid #000000'
          handle.style.cursor = 'nwse-resize'
          handle.style.zIndex = '10002'
          handle.style.touchAction = 'none'
          el.appendChild(handle)

          // Add delete toolbar (top-right)
          const del = document.createElement('button')
          del.setAttribute('data-testid', 'redaction-delete')
          del.textContent = '×'
          del.title = 'Delete redaction'
          del.style.position = 'absolute'
          del.style.right = '-2px'
          del.style.top = '-2px'
          del.style.width = '20px'
          del.style.height = '20px'
          del.style.background = '#ef4444'
          del.style.color = 'white'
          del.style.border = '2px solid white'
          del.style.cursor = 'pointer'
          del.style.fontSize = '14px'
          del.style.fontWeight = 'bold'
          del.style.borderRadius = '50%'
          del.style.zIndex = '10003'
          del.style.display = 'flex'
          del.style.alignItems = 'center'
          del.style.justifyContent = 'center'
          del.style.lineHeight = '1'
          del.style.pointerEvents = 'auto'
          del.style.touchAction = 'none'
          el.appendChild(del)

          // Drag/resize handlers (image pixel coordinates)
          const id = (r as any).id as number | undefined
          const getImageRect = () => ({ x1: xRaw, y1: yRaw, x2: xRaw + wRaw, y2: yRaw + hRaw })
          el.addEventListener('mousedown', (e) => {
            if (!id || (e.target as HTMLElement) === handle || (e.target as HTMLElement) === del) return
            e.preventDefault()
            e.stopPropagation()
            // Disable redaction drawing when interacting with existing redaction
            isDrawingRef.current = false
            suppressCanvasInteractionsRef.current = true
            try { if (viewer && (viewer as any).setMouseNavEnabled && (viewer as any).tracker) { (viewer as any).setMouseNavEnabled(false) } } catch {}
            const pt = viewer.viewport.pointFromPixel(new OpenSeadragon.Point(e.clientX, e.clientY))
            const imgPt = tiledImage ? tiledImage.viewportToImageCoordinates(pt) : { x: pt.x * 3000, y: pt.y * 3000 }
            draggingRef.current = { id, startX: imgPt.x, startY: imgPt.y, orig: getImageRect() }
            activeOverlayElRef.current = el
            logEvent('Redactions', 'Start drag', { id, imgX: imgPt.x, imgY: imgPt.y, clientX: e.clientX, clientY: e.clientY })
            try { (el as HTMLElement).style.boxShadow = '0 0 0 2px rgba(59,130,246,0.6) inset' } catch {}
          })
          handle.addEventListener('mousedown', (e) => {
            if (!id) return
            e.stopPropagation()
            e.preventDefault()
            // Disable redaction drawing when resizing
            isDrawingRef.current = false
            suppressCanvasInteractionsRef.current = true

            // Disable OpenSeadragon mouse tracking during resize
            try { if (viewer && (viewer as any).setMouseNavEnabled && (viewer as any).tracker) { (viewer as any).setMouseNavEnabled(false) } } catch {}

            const pt = viewer.viewport.pointFromPixel(new OpenSeadragon.Point((e as MouseEvent).clientX, (e as MouseEvent).clientY))
            const imgPt = tiledImage ? tiledImage.viewportToImageCoordinates(pt) : { x: pt.x * 3000, y: pt.y * 3000 }
            resizingRef.current = { id, startX: imgPt.x, startY: imgPt.y, orig: getImageRect() }
            activeOverlayElRef.current = el
            logEvent('Redactions', 'Start resize', { id, imgX: imgPt.x, imgY: imgPt.y, clientX: (e as MouseEvent).clientX, clientY: (e as MouseEvent).clientY })
            try { (el as HTMLElement).style.boxShadow = '0 0 0 2px rgba(59,130,246,0.6) inset' } catch {}
          })

          del.addEventListener('click', (e) => {
            e.stopPropagation()
            e.preventDefault()
            // Suppress OSD interactions during delete click
            suppressCanvasInteractionsRef.current = true
            if (!id) return
            logEvent('Redactions', 'Delete clicked', { id, el: el.getAttribute('data-redaction-id') })
            if (confirm('Delete this redaction?')) {
              onRedactionDelete?.(id)
            }
          })
        })
    }

    // Comment pin overlays
    if (showAnnotations) {
      const pageComments = comments.filter(c => c.page_number === pageNumber)
      console.log('💬 COMMENT PINS:', pageComments.length, 'pins on page', pageNumber, 'showAnnotations:', showAnnotations)
      pageComments.forEach((c) => {
          const wrapper = document.createElement('div')
          wrapper.style.pointerEvents = 'auto'
          wrapper.style.position = 'absolute'
          wrapper.style.zIndex = '9999'

          const pin = document.createElement('div')
          pin.style.width = '16px'
          pin.style.height = '16px'
          pin.style.borderRadius = '50%'
          pin.style.background = '#2563eb'
          pin.style.boxShadow = '0 0 0 3px rgba(37,99,235,0.5), 0 0 10px rgba(37,99,235,0.3)'
          pin.style.cursor = 'pointer'
          pin.style.border = '2px solid white'
          pin.style.position = 'relative'
          pin.style.zIndex = '10000'
          pin.title = c.content || 'Comment'
          pin.setAttribute('data-testid', 'comment-pin')

          // Enhanced styling applied

          const bubble = document.createElement('div')
          bubble.style.position = 'absolute'
          bubble.style.left = '16px'
          bubble.style.top = '-4px'
          bubble.style.transform = 'translateY(-100%)'
          bubble.style.maxWidth = '240px'
          bubble.style.background = 'white'
          bubble.style.border = '1px solid rgba(0,0,0,0.1)'
          bubble.style.boxShadow = '0 10px 20px rgba(0,0,0,0.08)'
          bubble.style.borderRadius = '8px'
          bubble.style.padding = '8px 10px'
          bubble.style.fontSize = '12px'
          bubble.style.color = '#111827'
          bubble.style.display = 'none'
          bubble.style.zIndex = '1001'
          bubble.textContent = c.content || 'Comment'

          pin.addEventListener('click', (e) => {
            e.stopPropagation()
            // Use requestAnimationFrame to improve performance
            requestAnimationFrame(() => {
              bubble.style.display = bubble.style.display === 'none' ? 'block' : 'none'
            })
          })

          wrapper.appendChild(pin)
          wrapper.appendChild(bubble)

          const isPixel = c.x_position > 1 || c.y_position > 1
          let rect: OpenSeadragon.Rect
          if (isPixel && tiledImage) {
            const sizePx = 12
            const imageRect = new OpenSeadragon.Rect(c.x_position - sizePx / 2, c.y_position - sizePx / 2, sizePx, sizePx)
            rect = tiledImage.imageToViewportRectangle(imageRect)
          } else {
            // Fallback: treat coordinates as normalized viewport coordinates
            const size = 0.012
            const x = (c.x_position / 2550) - size / 2
            const y = (c.y_position / 3300) - size / 2
            rect = new OpenSeadragon.Rect(x, y, size, size)
          }
                    try {
            console.log('🎯 Comment coords:', { id: (c as any).id, x: c.x_position, y: c.y_position, rect: { x: rect.x, y: rect.y, width: rect.width, height: rect.height } })
            viewer.addOverlay({ element: wrapper, location: rect })
            console.log('✅ Comment pin added:', (c as any).id)
          } catch (err) {
            console.error('❌ Comment pin failed:', (c as any).id, err)
          }
          overlaysRef.current.push({ type: 'comment', el: wrapper })
        })
    }
  }, [viewer, redactions, comments, pageNumber, showRedactions, showAnnotations])

  // Delegated event handlers to ensure interactions are captured reliably
  useEffect(() => {
    if (!viewerRef.current || !viewer) return
    const root = viewerRef.current
    const tiledImage = viewer.world.getItemAt(0)

    const onClickCapture = (e: Event) => {
      const target = e.target as HTMLElement
      if (!target) return
      if (target.getAttribute('data-testid') === 'redaction-delete') {
        const parent = target.parentElement as HTMLElement | null
        const idStr = parent?.getAttribute('data-redaction-id')
        if (idStr) {
          e.stopPropagation()
          e.preventDefault()
          const id = Number(idStr)
          logEvent('Redactions', 'Delete clicked (delegated)', { id })
          if (confirm('Delete this redaction?')) {
            onRedactionDelete?.(id)
          }
        }
      }
    }

    const onMouseDownCapture = (ev: MouseEvent | PointerEvent) => {
      const target = ev.target as HTMLElement
      if (!target) return
      const isHandle = target.getAttribute('data-testid') === 'redaction-resize-handle'
      const isOverlay = target.getAttribute('data-testid') === 'redaction-overlay'
      if (!isHandle && !isOverlay) return
      const el = isHandle ? (target.parentElement as HTMLElement | null) : target
      if (!el) return
      const idStr = el.getAttribute('data-redaction-id')
      if (!idStr) return
      const id = Number(idStr)
      ev.stopPropagation()
      ev.preventDefault()
      isDrawingRef.current = false
      suppressCanvasInteractionsRef.current = true
      viewer.setMouseNavEnabled(false)
      activeOverlayElRef.current = el
      try { el.style.boxShadow = '0 0 0 2px rgba(59,130,246,0.6) inset' } catch {}

      const pt = viewer.viewport.pointFromPixel(new OpenSeadragon.Point((ev as any).clientX, (ev as any).clientY))
      const imgPt = tiledImage ? tiledImage.viewportToImageCoordinates(pt) : { x: pt.x * 3000, y: pt.y * 3000 }
      const orig = {
        x1: Number(el.dataset.x1 || '0'),
        y1: Number(el.dataset.y1 || '0'),
        x2: Number(el.dataset.x2 || '0'),
        y2: Number(el.dataset.y2 || '0'),
      }
      if (isHandle) {
        resizingRef.current = { id, startX: imgPt.x, startY: imgPt.y, orig }
        logEvent('Redactions', 'Start resize (delegated)', { id, imgX: imgPt.x, imgY: imgPt.y })
      } else {
        draggingRef.current = { id, startX: imgPt.x, startY: imgPt.y, orig }
        logEvent('Redactions', 'Start drag (delegated)', { id, imgX: imgPt.x, imgY: imgPt.y })
      }
    }

    root.addEventListener('click', onClickCapture, true)
    root.addEventListener('mousedown', onMouseDownCapture as any, true)
    root.addEventListener('pointerdown', onMouseDownCapture as any, true)
    return () => {
      root.removeEventListener('click', onClickCapture, true)
      root.removeEventListener('mousedown', onMouseDownCapture as any, true)
      root.removeEventListener('pointerdown', onMouseDownCapture as any, true)
    }
  }, [viewer, onRedactionDelete])

  // Debug: Log when overlay effect runs
  useEffect(() => {
    console.log('🔍 OVERLAY EFFECT:', {
      hasViewer: !!viewer,
      commentsCount: comments.length,
      redactionsCount: redactions.length,
      pageNumber,
      showAnnotations,
      showRedactions
    })
  }, [viewer, redactions, comments, pageNumber, showRedactions, showAnnotations])

  // Global mouse handlers for drag/resize
  useEffect(() => {
    if (!viewer) return
    const onMove = (e: MouseEvent) => {
      const tiledImageMove = viewer.world.getItemAt(0)
      if (!tiledImageMove) return
      if (draggingRef.current) {
        const { id, startX, startY, orig } = draggingRef.current
        const vp = viewer.viewport.pointFromPixel(new OpenSeadragon.Point(e.clientX, e.clientY))
        const img = tiledImageMove ? tiledImageMove.viewportToImageCoordinates(vp) : { x: vp.x * 3000, y: vp.y * 3000 }
        // Bounds
        let maxW = 3000
        let maxH = 4000
        try {
          const size = (tiledImageMove as any).getContentSize?.()
          if (size && typeof size.x === 'number' && typeof size.y === 'number') { maxW = size.x; maxH = size.y }
        } catch {}
        const dx = img.x - startX
        const dy = img.y - startY
        let x1 = orig.x1 + dx
        let y1 = orig.y1 + dy
        let x2 = orig.x2 + dx
        let y2 = orig.y2 + dy
        // Clamp
        x1 = Math.max(0, Math.min(maxW, x1))
        y1 = Math.max(0, Math.min(maxH, y1))
        x2 = Math.max(0, Math.min(maxW, x2))
        y2 = Math.max(0, Math.min(maxH, y2))
        // Live-update overlay position visually without API call
        try {
          const rect = tiledImageMove.imageToViewportRectangle(new OpenSeadragon.Rect(Math.min(x1, x2), Math.min(y1, y2), Math.abs(x2 - x1), Math.abs(y2 - y1)))
          if (activeOverlayElRef.current) {
            viewer.updateOverlay(activeOverlayElRef.current, rect)
          }
        } catch {}
        pendingUpdateRef.current = { id, x1: Math.min(x1, x2), y1: Math.min(y1, y2), x2: Math.max(x1, x2), y2: Math.max(y1, y2) }
        draggingRef.current = { id, startX, startY, orig }
      } else if (resizingRef.current) {
        const { id, startX, startY, orig } = resizingRef.current
        const vp = viewer.viewport.pointFromPixel(new OpenSeadragon.Point(e.clientX, e.clientY))
        const img = tiledImageMove ? tiledImageMove.viewportToImageCoordinates(vp) : { x: vp.x * 3000, y: vp.y * 3000 }
        // Bounds
        let maxW = 3000
        let maxH = 4000
        try {
          const size = (tiledImageMove as any).getContentSize?.()
          if (size && typeof size.x === 'number' && typeof size.y === 'number') { maxW = size.x; maxH = size.y }
        } catch {}
        const dx = img.x - startX
        const dy = img.y - startY
        const x1 = orig.x1
        const y1 = orig.y1
        let x2 = Math.max(x1 + 2, orig.x2 + dx)
        let y2 = Math.max(y1 + 2, orig.y2 + dy)
        // Clamp
        x2 = Math.max(0, Math.min(maxW, x2))
        y2 = Math.max(0, Math.min(maxH, y2))
        try {
          const rect = tiledImageMove.imageToViewportRectangle(new OpenSeadragon.Rect(Math.min(x1, x2), Math.min(y1, y2), Math.abs(x2 - x1), Math.abs(y2 - y1)))
          if (activeOverlayElRef.current) {
            viewer.updateOverlay(activeOverlayElRef.current, rect)
          }
        } catch {}
        pendingUpdateRef.current = { id, x1: Math.min(x1, x2), y1: Math.min(y1, y2), x2: Math.max(x1, x2), y2: Math.max(y1, y2) }
        resizingRef.current = { id, startX, startY, orig }
      }
    }
    const onUp = () => {
      // Re-enable OpenSeadragon mouse tracking
      try { if (viewer && (viewer as any).setMouseNavEnabled && (viewer as any).tracker) { (viewer as any).setMouseNavEnabled(true) } } catch {}
      suppressCanvasInteractionsRef.current = false
      // Commit pending update once on mouseup
      if (pendingUpdateRef.current) {
        const { id, x1, y1, x2, y2 } = pendingUpdateRef.current
        onRedactionUpdate?.({ id, page_number: pageNumber, x_start: x1, y_start: y1, x_end: x2, y_end: y2 })
        pendingUpdateRef.current = null
      }
      activeOverlayElRef.current = null
      draggingRef.current = null
      resizingRef.current = null
    }
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
    return () => {
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
    }
  }, [viewer, pageNumber, onRedactionUpdate])

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
      {/* Mode Indicator */}
      {(commentMode || redactionMode) && (
        <div className="absolute top-2 left-1/2 transform -translate-x-1/2 z-50 px-3 py-1 rounded-full text-xs font-medium bg-white shadow-lg">
          {commentMode && <span className="text-blue-700">💬 Click anywhere to add comment</span>}
          {redactionMode && <span className="text-red-700">✏️ Drag to draw redaction rectangle</span>}
        </div>
      )}

      {/* Viewer Container */}
            {useImageFallback ? (
        <ImageFallbackViewer
          documentId={documentId}
          pageNumber={pageNumber}
          commentMode={commentMode}
          redactionMode={redactionMode}
          onAddCommentAt={onAddCommentAt}
          onRedactionCreate={onRedactionCreate}
          onRedactionUpdate={onRedactionUpdate}
          onRedactionDelete={onRedactionDelete}
          comments={comments}
          redactions={redactions}
        />

      ) : (
        <div ref={viewerRef} data-testid="viewer-container" className="document-viewer w-full h-full min-h-[600px]" />
      )}

      {/* Toolbar */}
      <div className="absolute top-4 left-4 bg-white rounded-lg shadow-lg p-2 flex items-center space-x-2">
        <button
          onClick={handleZoomIn}
          data-testid="zoom-in"
          className="p-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded transition-colors"
          title="Zoom In"
        >
          <ZoomIn className="h-4 w-4" />
        </button>
        <button
          onClick={handleZoomOut}
          data-testid="zoom-out"
          className="p-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded transition-colors"
          title="Zoom Out"
        >
          <ZoomOut className="h-4 w-4" />
        </button>
        <button
          onClick={handleZoomHome}
          data-testid="fit-to-screen"
          className="p-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded transition-colors"
          title="Fit to Screen"
        >
          <Home className="h-4 w-4" />
        </button>
        <button
          onClick={handleRotate}
          data-testid="rotate"
          className="p-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded transition-colors"
          title="Rotate"
        >
          <RotateCw className="h-4 w-4" />
        </button>
        <button
          onClick={handleFullscreen}
          data-testid="fullscreen"
          className="p-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded transition-colors"
          title="Fullscreen"
        >
          <Maximize className="h-4 w-4" />
        </button>
      </div>

      {/* Inline OSD comment input */}
      {showOsdCommentInput && (
        <div
          className="absolute z-50 bg-white border border-gray-300 rounded-lg shadow-lg p-2"
          style={{ left: osdCommentPos.x, top: osdCommentPos.y - 60, minWidth: 220 }}
        >
          <textarea
            className="w-full p-2 border border-gray-200 rounded text-sm resize-none"
            placeholder="Enter your comment..."
            rows={3}
            value={osdCommentText}
            onChange={(e) => setOsdCommentText(e.target.value)}
            autoFocus
          />
          <div className="flex justify-end space-x-2 mt-2">
            <button
              onClick={() => { setShowOsdCommentInput(false); setOsdCommentText(''); osdPendingCommentRef.current = null }}
              className="px-3 py-1 text-xs text-gray-600 hover:text-gray-800"
            >
              Cancel
            </button>
            <button
              onClick={() => {
                if (!osdCommentText.trim() || !osdPendingCommentRef.current) return
                const { x, y, page } = osdPendingCommentRef.current
                ;(window as any).tempCommentText = osdCommentText.trim()
                onAddCommentAt?.(x, y, page)
                setShowOsdCommentInput(false)
                setOsdCommentText('')
                osdPendingCommentRef.current = null
              }}
              className="px-3 py-1 text-xs bg-blue-600 text-white rounded hover:bg-blue-700"
            >
              Add
            </button>
          </div>
        </div>
      )}

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
          onClick={() => setInternalShowAnnotations(!showAnnotations)}
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
          onClick={() => setInternalShowRedactions(!showRedactions)}
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

      {/* Comment Modal for Existing Comments */}
      {showCommentModal && selectedComment && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4">
            <div className="flex justify-between items-start mb-4">
              <h3 className="text-lg font-semibold text-gray-900">Comment</h3>
              <button
                onClick={() => setShowCommentModal(false)}
                className="text-gray-400 hover:text-gray-600"
              >
                ×
              </button>
            </div>
            <div className="mb-4">
              <p className="text-gray-700">{selectedComment.content}</p>
              <p className="text-sm text-gray-500 mt-2">
                Created: {new Date(selectedComment.created_at || Date.now()).toLocaleString()}
              </p>
            </div>
            <div className="flex justify-end space-x-2">
              <button
                onClick={() => setShowCommentModal(false)}
                className="px-4 py-2 bg-gray-200 text-gray-800 rounded hover:bg-gray-300"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
