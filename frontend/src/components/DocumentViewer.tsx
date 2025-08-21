import React, { useEffect, useRef, useState, useCallback } from 'react'
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
  comments,
  redactions
}: {
  documentId: number
  pageNumber: number
  commentMode: boolean
  redactionMode: boolean
  onAddCommentAt?: (x: number, y: number, page: number) => void
  onRedactionCreate?: (redaction: any) => void
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
        src={`/api/documents/${documentId}/thumbnail/${pageNumber}`}
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
              className="absolute bg-black bg-opacity-90 border border-red-500 z-15 cursor-pointer"
              style={{ left: x, top: y, width, height }}
              title={`Redaction: ${redaction.reason || 'No reason'}`}
            />
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
                  const img = document.querySelector(`img[src*="/api/documents/${documentId}/thumbnail/${pageNumber}"]`) as HTMLImageElement
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
  const isDrawingRef = useRef(false)
  const drawStartRef = useRef<{x: number, y: number} | null>(null)
  const currentRedactionRef = useRef<HTMLDivElement | null>(null)
  const overlaysRef = useRef<{ type: 'redaction' | 'comment'; el: HTMLElement }[]>([])
  const draggingRef = useRef<{ id: number; startX: number; startY: number; orig: { x1: number; y1: number; x2: number; y2: number } } | null>(null)
  const resizingRef = useRef<{ id: number; startX: number; startY: number; orig: { x1: number; y1: number; x2: number; y2: number } } | null>(null)

  useEffect(() => {
    if (!viewerRef.current) return

    // Initialize OpenSeadragon viewer
    const osdViewer = OpenSeadragon({
      element: viewerRef.current,
      prefixUrl: '/openseadragon-images/',
      tileSources: {
        type: 'image',
        url: `/api/documents/${documentId}/thumbnail/${pageNumber}`,
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
      maxZoomLevel: 20,
      defaultZoomLevel: 1.0,
    })

    // If OSD fails to open quickly, fall back to simple <img>
    const fallbackTimer = window.setTimeout(() => {
      try {
        const count = osdViewer.world.getItemCount()
        if (count === 0) setUseImageFallback(true)
      } catch {
        setUseImageFallback(true)
      }
    }, 1500)

    // Handle single clicks to add comments (when in comment mode)
    osdViewer.addHandler('canvas-click', (event: any) => {
      console.log('🔍 OSD canvas-click:', { commentMode, redactionMode })
      if (redactionMode) return
      if (!commentMode || !onAddCommentAt) return
      const item = osdViewer.world.getItemAt(0)
      if (!item) return
      const vpPoint = osdViewer.viewport.pointFromPixel(event.position)
      const imgPoint = item.viewportToImageCoordinates(vpPoint)
      console.log('🔍 OSD comment click at:', imgPoint.x, imgPoint.y)
      onAddCommentAt(imgPoint.x, imgPoint.y, pageNumber)
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

        // Add redaction drawing handlers
    if (redactionMode) {
      console.log('🔍 OSD: Setting up redaction handlers')

      // Disable pan/zoom during redaction mode
      osdViewer.panHorizontal = false
      osdViewer.panVertical = false
      osdViewer.zoomPerClick = 1.0
      osdViewer.zoomPerScroll = 1.0

      osdViewer.addHandler('canvas-press', (event: any) => {
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

          // Calculate redaction coordinates in IMAGE PIXELS
          const x_start = Math.min(startImage.x, endImage.x)
          const y_start = Math.min(startImage.y, endImage.y)
          const x_end = Math.max(startImage.x, endImage.x)
          const y_end = Math.max(startImage.y, endImage.y)

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
          el.style.background = 'rgba(0,0,0,0.85)'
          el.style.border = '1px solid rgba(0,0,0,0.9)'
          el.style.pointerEvents = 'auto'
          el.style.cursor = 'move'
          el.style.position = 'relative'
          const xRaw = Math.min(r.x_start, r.x_end)
          const yRaw = Math.min(r.y_start, r.y_end)
          const wRaw = Math.abs(r.x_end - r.x_start)
          const hRaw = Math.abs(r.y_end - r.y_start)
          let rect: OpenSeadragon.Rect
          const isPixel = xRaw > 1 || yRaw > 1 || wRaw > 1 || hRaw > 1
          if (isPixel && tiledImage) {
            const imageRect = new OpenSeadragon.Rect(xRaw, yRaw, wRaw, hRaw)
            rect = tiledImage.imageToViewportRectangle(imageRect)
          } else {
            // Fallback: treat coordinates as normalized viewport coordinates
            rect = new OpenSeadragon.Rect(xRaw / 3000, yRaw / 3000, wRaw / 3000, hRaw / 3000)
          }
          try { viewer.addOverlay({ element: el, location: rect }) } catch {}
          overlaysRef.current.push({ type: 'redaction', el })

          // Add resize handle (bottom-right)
          const handle = document.createElement('div')
          handle.style.position = 'absolute'
          handle.style.width = '10px'
          handle.style.height = '10px'
          handle.style.right = '0'
          handle.style.bottom = '0'
          handle.style.background = '#ffffff'
          handle.style.border = '1px solid #000000'
          handle.style.cursor = 'nwse-resize'
          el.appendChild(handle)

          // Add delete toolbar (top-right)
          const del = document.createElement('button')
          del.textContent = '×'
          del.title = 'Delete redaction'
          del.style.position = 'absolute'
          del.style.right = '0'
          del.style.top = '0'
          del.style.width = '16px'
          del.style.height = '16px'
          del.style.background = '#ef4444'
          del.style.color = 'white'
          del.style.border = 'none'
          del.style.cursor = 'pointer'
          del.style.fontSize = '12px'
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
            const pt = viewer.viewport.pointFromPixel(new OpenSeadragon.Point(e.clientX, e.clientY))
            const imgPt = tiledImage ? tiledImage.viewportToImageCoordinates(pt) : { x: pt.x * 3000, y: pt.y * 3000 }
            draggingRef.current = { id, startX: imgPt.x, startY: imgPt.y, orig: getImageRect() }
            console.log('🔧 Starting redaction drag:', id, 'at', imgPt)
          })
          handle.addEventListener('mousedown', (e) => {
            if (!id) return
            e.stopPropagation()
            e.preventDefault()
            // Disable redaction drawing when resizing
            isDrawingRef.current = false
            const pt = viewer.viewport.pointFromPixel(new OpenSeadragon.Point((e as MouseEvent).clientX, (e as MouseEvent).clientY))
            const imgPt = tiledImage ? tiledImage.viewportToImageCoordinates(pt) : { x: pt.x * 3000, y: pt.y * 3000 }
            resizingRef.current = { id, startX: imgPt.x, startY: imgPt.y, orig: getImageRect() }
            console.log('🔧 Starting redaction resize:', id, 'at', imgPt)
          })

          del.addEventListener('click', (e) => {
            e.stopPropagation()
            e.preventDefault()
            if (!id) return
            console.log('🗑️ REDACTION DELETE CLICKED:', id)
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
            const x = (c.x_position / 3000) - size / 2
            const y = (c.y_position / 3000) - size / 2
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
        const dx = img.x - startX
        const dy = img.y - startY
        const x1 = orig.x1 + dx
        const y1 = orig.y1 + dy
        const x2 = orig.x2 + dx
        const y2 = orig.y2 + dy
        console.log('🔧 Dragging redaction:', id, 'to', { x1, y1, x2, y2 })
        onRedactionUpdate?.({ id, page_number: pageNumber, x_start: x1, y_start: y1, x_end: x2, y_end: y2 })
        draggingRef.current = { id, startX, startY, orig }
      } else if (resizingRef.current) {
        const { id, startX, startY, orig } = resizingRef.current
        const vp = viewer.viewport.pointFromPixel(new OpenSeadragon.Point(e.clientX, e.clientY))
        const img = tiledImageMove ? tiledImageMove.viewportToImageCoordinates(vp) : { x: vp.x * 3000, y: vp.y * 3000 }
        const dx = img.x - startX
        const dy = img.y - startY
        const x1 = orig.x1
        const y1 = orig.y1
        const x2 = Math.max(x1 + 2, orig.x2 + dx)
        const y2 = Math.max(y1 + 2, orig.y2 + dy)
        console.log('🔧 Resizing redaction:', id, 'to', { x1, y1, x2, y2 })
        onRedactionUpdate?.({ id, page_number: pageNumber, x_start: x1, y_start: y1, x_end: x2, y_end: y2 })
        resizingRef.current = { id, startX, startY, orig }
      }
    }
    const onUp = () => {
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
    </div>
  )
}
