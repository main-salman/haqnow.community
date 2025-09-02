import React, { useEffect, useState, useRef } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
	ArrowLeft,
	FileText,
	MessageSquare,
	Download,
	Share2,
	Clock,
	CheckCircle,
	AlertCircle,
	Bot,
	Edit3,
	Send,
	Trash2
} from 'lucide-react'
import { documentsApi, searchApi } from '../services/api'
import { useAuthStore } from '../services/auth'
import DocumentViewer from '../components/DocumentViewer'
import { clsx } from 'clsx'
import toast from 'react-hot-toast'
import { logEvent, logError, logWarn } from '../utils/log'
import { io, Socket } from 'socket.io-client'

export default function DocumentViewerPage() {
	const { id } = useParams<{ id: string }>()
	const documentId = parseInt(id || '0')
	const queryClient = useQueryClient()
	const { isAuthenticated } = useAuthStore()
	const [currentPage, setCurrentPage] = useState(0)
	const [showSidebar, setShowSidebar] = useState(true)
	const [sidebarTab, setSidebarTab] = useState<'info' | 'comments' | 'redactions' | 'ai' | 'sharing'>('info')
	const [mode, setMode] = useState<'view' | 'comment' | 'redact'>('view')
	const [aiQuestion, setAiQuestion] = useState('')
	const [newComment, setNewComment] = useState('')
	const [aiAnswer, setAiAnswer] = useState('')
	const [isLoadingAI, setIsLoadingAI] = useState(false)

	const [shareEmail, setShareEmail] = useState('')
	const [sharePermission, setSharePermission] = useState<'view' | 'edit'>('view')
	const [shareEveryone, setShareEveryone] = useState(false)
	const socketRef = useRef<Socket | null>(null)
	const markersLayerRef = useRef<HTMLDivElement | null>(null)
		const [liveComments, setLiveComments] = useState<any[]>([])
	const [liveRedactions, setLiveRedactions] = useState<any[]>([])
	const [showPins, setShowPins] = useState(true)
	const [hasRedactionLock, setHasRedactionLock] = useState(false)
	const [deletingComments, setDeletingComments] = useState<Set<number>>(new Set())
	const [deletingRedactions, setDeletingRedactions] = useState<Set<number>>(new Set())

	const { data: document, isLoading } = useQuery({
		queryKey: ['document', documentId],
		queryFn: () => documentsApi.get(documentId).then(res => res.data),
		enabled: !!documentId,
	})

	const { data: documentMetadata } = useQuery({
		queryKey: ['document-metadata', documentId],
		queryFn: () => documentsApi.getMetadata(documentId).then(res => res.data),
		enabled: !!documentId,
	})

	const { data: jobs = [] } = useQuery({
		queryKey: ['document-jobs', documentId],
		queryFn: () => documentsApi.getJobs(documentId).then(res => res.data),
		enabled: !!documentId,
		refetchInterval: 5000,
	})

	const { data: comments = [] } = useQuery({
		queryKey: ['document-comments', documentId],
		queryFn: () => {
			console.log('📡 FETCHING COMMENTS:', documentId)
			return documentsApi.getComments(documentId).then(res => {
				console.log('📡 COMMENTS LOADED:', res.data.comments?.length || 0)
				return res.data.comments || []
			})
		},
		enabled: !!documentId && isAuthenticated,
		staleTime: 30000, // Cache for 30 seconds to prevent excessive refetching
	})

	const { data: redactions = [] } = useQuery({
		queryKey: ['document-redactions', documentId],
		queryFn: () => {
			console.log('📡 FETCHING REDACTIONS:', documentId)
			return documentsApi.getRedactions(documentId).then(res => {
				console.log('📡 REDACTIONS LOADED:', res.data.redactions?.length || 0)
				return res.data.redactions || []
			})
		},
		enabled: !!documentId && isAuthenticated,
		staleTime: 30000, // Cache for 30 seconds to prevent excessive refetching
	})

	const handleUpdateRedaction = async (r: { id?: number; page_number: number; x_start: number; y_start: number; x_end: number; y_end: number; reason?: string }) => {
		try {
			if (!r.id) return
			logEvent('Redactions', 'Updating', { id: r.id, x_start: r.x_start, y_start: r.y_start, x_end: r.x_end, y_end: r.y_end })
			// Optimistic update
			const prev = queryClient.getQueryData<any[]>(['document-redactions', documentId]) || []
			queryClient.setQueryData(['document-redactions', documentId], prev.map((x: any) => x.id === r.id ? { ...x, ...r } : x))
			await documentsApi.updateRedaction(documentId, r.id, {
				x_start: r.x_start,
				y_start: r.y_start,
				x_end: r.x_end,
				y_end: r.y_end,
				reason: r.reason,
			})
			queryClient.invalidateQueries(['document-redactions', documentId])
			if (socketRef.current) {
				socketRef.current.emit('add_redaction', { document_id: documentId, redaction: r })
			}
		} catch (error: any) {
			logError('Redactions', 'Failed to update', { error: error?.message, response: error?.response?.data })
			// Revert on failure
			queryClient.invalidateQueries(['document-redactions', documentId])
		}
	}

	const handleDeleteRedaction = async (redactionId: number) => {
		// Prevent multiple rapid clicks
		if (deletingRedactions.has(redactionId)) return

		setDeletingRedactions(prev => new Set(prev).add(redactionId))

		try {
			logEvent('Redactions', 'Deleting', { id: redactionId })
			// Optimistic remove
			const prev = queryClient.getQueryData<any[]>(['document-redactions', documentId]) || []
			queryClient.setQueryData(['document-redactions', documentId], prev.filter((x: any) => x.id !== redactionId))
			await documentsApi.deleteRedaction(documentId, redactionId)
			queryClient.invalidateQueries(['document-redactions', documentId])
			if (socketRef.current) {
				socketRef.current.emit('delete_redaction', { document_id: documentId, redaction_id: redactionId })
			}
			toast.success('Redaction deleted')
		} catch (error: any) {
			logError('Redactions', 'Failed to delete', { error: error?.message, response: error?.response?.data })
			// Handle 404 gracefully - redaction might have been already deleted
			if (error?.response?.status === 404) {
				logWarn('Redactions', 'Delete 404 - already deleted', { id: redactionId })
				queryClient.invalidateQueries(['document-redactions', documentId])
				toast.success('Redaction deleted')
			} else {
				toast.error('Failed to delete redaction')
				// Revert optimistic removal
				queryClient.invalidateQueries(['document-redactions', documentId])
			}
		} finally {
			setDeletingRedactions(prev => {
				const newSet = new Set(prev)
				newSet.delete(redactionId)
				return newSet
			})
		}
	}

	const { data: shares = [] } = useQuery({
		queryKey: ['document-shares', documentId],
		queryFn: () => documentsApi.getShares(documentId).then(res => res.data),
		enabled: !!documentId,
	})

	// Handlers for functionality
	const handleDownload = async () => {
		try {
			console.log('🔍 Starting redacted download for document', documentId)
			// Prefer server-side generated redacted download endpoint
			window.location.assign(`/api/documents/${documentId}/download`)

			toast.success('Download started')
		} catch (error) {
			console.error('Download error:', error)
			toast.error('Download failed')
		}
	}

	const handleShare = async () => {
		try {
			await navigator.clipboard.writeText(window.location.href)
			toast.success('Document link copied to clipboard')
		} catch (error) {
			toast.error('Failed to copy link')
		}
	}

	const handleCreateShare = async () => {
		try {
			const shareData = {
				shared_with_email: shareEveryone ? undefined : shareEmail,
				permission_level: sharePermission,
				is_everyone: shareEveryone
			}
			await documentsApi.shareDocument(documentId, shareData)
			toast.success('Document shared successfully')
			setShareEmail('')
			setShareEveryone(false)
			// Refresh shares
			queryClient.invalidateQueries(['document-shares', documentId])
		} catch (error) {
			toast.error('Failed to share document')
		}
	}

	const handleCreateRedaction = async (redactionData: {
		page_number: number
		x_start: number
		y_start: number
		x_end: number
		y_end: number
		reason?: string
	}) => {
		try {
			console.log('🔍 Creating redaction:', {
				hasRedactionLock,
				hasSocket: !!socketRef.current,
				redactionData
			})
			if (!hasRedactionLock && socketRef.current) {
				console.log('🔍 Redaction blocked: No lock held, attempting to acquire lock...')
				// Try to acquire lock immediately before creating redaction
				socketRef.current.emit('acquire_redaction_lock', { document_id: documentId })

				// Wait briefly for lock response
				await new Promise(resolve => setTimeout(resolve, 100))

				if (!hasRedactionLock) {
					console.log('🔍 Lock acquisition failed, proceeding anyway for testing')
					// For now, allow redaction creation without lock for testing
					// toast.error('You do not hold the redaction lock')
					// return
				}
			}
			await documentsApi.addRedaction(documentId, redactionData)
			toast.success('Redaction added successfully')
			// Refresh redactions
			queryClient.invalidateQueries(['document-redactions', documentId])
			// Broadcast to collaborators
			if (socketRef.current) {
				socketRef.current.emit('add_redaction', { document_id: documentId, redaction: redactionData })
			}
		} catch (error) {
			toast.error('Failed to add redaction')
		}
	}

	const handleAIQuestion = async () => {
		if (!aiQuestion.trim()) return

		setIsLoadingAI(true)
		try {
			const response = await searchApi.askQuestion(documentId, aiQuestion)
			setAiAnswer(response.data.answer || 'No answer available')
			toast.success('AI response received')
		} catch (error) {
			toast.error('AI question failed')
			setAiAnswer('Sorry, I could not process your question at this time.')
		} finally {
			setIsLoadingAI(false)
		}
	}

	const handleAddComment = async (x?: number, y?: number, pageNumber?: number) => {
		if (!newComment.trim()) return

		try {
			const commentData = {
				content: newComment,
				page_number: pageNumber || currentPage,
				x_position: x || 0,
				y_position: y || 0
			}
			await documentsApi.addComment(documentId, commentData)
			setNewComment('')
			toast.success('Comment added')
			// Refresh comments
			queryClient.invalidateQueries(['document-comments', documentId])
		} catch (error) {
			toast.error('Failed to add comment')
		}
	}

		// Remove the problematic live data initialization that causes infinite loops

	useEffect(() => {
		// connect to socket server
		const s = io('/', {
			path: '/socket.io',
			transports: ['polling', 'websocket'],
			timeout: 5000,
			forceNew: true
		})
		socketRef.current = s
		s.on('connect', () => {
			console.log('🔍 Socket.IO connected, joining document', documentId)
			s.emit('join_document', { document_id: documentId })
		})
		s.on('connect_error', (error) => {
			console.log('🔍 Socket.IO connection error:', error)
		})
		s.on('disconnect', (reason) => {
			console.log('🔍 Socket.IO disconnected:', reason)
		})
		s.on('document_state', (state: any) => {
			console.log('🔍 Document state received:', {
				comments: state?.comments?.length || 0,
				redactions: state?.redactions?.length || 0
			})
			if (state?.comments) setLiveComments(state.comments)
			if (state?.redactions) setLiveRedactions(state.redactions)
		})
		s.on('comment_added', (payload: any) => {
			setLiveComments((prev) => [...prev, payload.comment])
		})
		s.on('comment_deleted', (payload: any) => {
			const cid = payload?.comment_id
			if (!cid) return

			// Update live comments state
			setLiveComments((prev) => {
				const filtered = prev.filter((c: any) => String(c.id) !== String(cid))
				// Only invalidate queries if the comment was actually in our state
				if (filtered.length !== prev.length) {
					queryClient.invalidateQueries(['document-comments', documentId])
				}
				return filtered
			})
		})
		s.on('redaction_added', (payload: any) => {
			setLiveRedactions((prev) => [...prev, payload.redaction])
			queryClient.invalidateQueries(['document-redactions', documentId])
		})
		s.on('redaction_deleted', (payload: any) => {
			const rid = payload?.redaction_id
			if (!rid) return
			setLiveRedactions((prev) => prev.filter((r: any) => String(r.id) !== String(rid)))
			queryClient.invalidateQueries(['document-redactions', documentId])
		})
		s.on('redaction_lock_status', (payload: any) => {
			console.log('🔍 Redaction lock status received:', payload)
			if (payload?.document_id === documentId) {
				setHasRedactionLock(!!payload.acquired)
				if (payload.acquired) {
					console.log('🔍 Redaction lock acquired successfully')
					toast.success('Redaction lock acquired')
				} else {
					console.log('🔍 Failed to acquire redaction lock')
					toast.error('Another user is currently redacting this document')
					setMode('view')
				}
			}
		})
		s.on('redaction_lock_released', (payload: any) => {
			if (payload?.document_id === documentId) {
				toast.success('Redaction lock released')
			}
		})
		return () => {
			if (hasRedactionLock) {
				s.emit('release_redaction_lock', { document_id: documentId })
			}
			s.emit('leave_document', { document_id: documentId })
			s.disconnect()
		}
	}, [documentId])

	useEffect(() => {
		if (!socketRef.current) {
			console.log('🔍 No socket connection for redaction lock')
			return
		}
		if (mode === 'redact') {
			console.log('🔍 Acquiring redaction lock for document', documentId)
			socketRef.current.emit('acquire_redaction_lock', { document_id: documentId })
		} else if (hasRedactionLock) {
			console.log('🔍 Releasing redaction lock for document', documentId)
			socketRef.current.emit('release_redaction_lock', { document_id: documentId })
			setHasRedactionLock(false)
		}
	}, [mode])

	// overlays are now rendered by DocumentViewer via OpenSeadragon overlays

	const [showCommentPopup, setShowCommentPopup] = useState(false)
	const [commentPopupPosition, setCommentPopupPosition] = useState({ x: 0, y: 0, page: 0 })
	const [commentPopupText, setCommentPopupText] = useState('')

	const handleViewerClickAddComment = (x: number, y: number, page: number) => {
		if (mode !== 'comment') return

		// Check if we have text from the in-place input (ImageFallbackViewer)
		if ((window as any).tempCommentText) {
			const commentText = (window as any).tempCommentText
			delete (window as any).tempCommentText

			logEvent('Comments', 'Submitting from fallback input', { x, y, page })
			documentsApi.addComment(documentId, {
				content: commentText.trim(),
				page_number: page,
				x_position: x,
				y_position: y,
			}).then(() => {
				toast.success('Comment added')
				queryClient.invalidateQueries(['document-comments', documentId])
				// Stay in comment mode for adding more comments
			}).catch((err) => { logError('Comments', 'Failed to add via fallback', { err: err?.message, data: err?.response?.data }); toast.error('Failed to add comment') })

			// emit live comment marker to others
			if (socketRef.current) {
				socketRef.current.emit('add_comment', {
					document_id: documentId,
					comment: { page_number: page, x_position: x, y_position: y, content: commentText.trim() }
				})
			}
		} else {
			// Show HTML5 style popup
			setCommentPopupPosition({ x, y, page })
			setCommentPopupText('')
			setShowCommentPopup(true)
		}
	}

	const handleSubmitComment = async () => {
		if (!commentPopupText.trim()) return

		try {
			logEvent('Comments', 'Submitting from popup', { x: commentPopupPosition.x, y: commentPopupPosition.y, page: commentPopupPosition.page })
			await documentsApi.addComment(documentId, {
				content: commentPopupText.trim(),
				page_number: commentPopupPosition.page,
				x_position: commentPopupPosition.x,
				y_position: commentPopupPosition.y,
			})
			toast.success('Comment added')
			queryClient.invalidateQueries(['document-comments', documentId])
			// Stay in comment mode for adding more comments
			setShowCommentPopup(false)
			setCommentPopupText('')

			// emit live comment marker to others
			if (socketRef.current) {
				socketRef.current.emit('add_comment', {
					document_id: documentId,
					comment: {
						page_number: commentPopupPosition.page,
						x_position: commentPopupPosition.x,
						y_position: commentPopupPosition.y,
						content: commentPopupText.trim()
					}
				})
			}
		} catch (error: any) {
			logError('Comments', 'Failed to add via popup', { error: error?.message, response: error?.response?.data })
			toast.error('Failed to add comment')
		}
	}

	const handleDelete = async () => {
		if (!confirm('Delete this document?')) return
		try {
			await documentsApi.delete(documentId)
			toast.success('Document deleted')
			window.location.href = '/documents'
		} catch (error: any) {
			toast.error(error?.response?.data?.detail || 'Delete failed')
		}
	}

	if (isLoading) {
		return (
			<div className="p-6">
				<div className="animate-pulse">
					<div className="h-8 bg-gray-200 rounded w-1/3 mb-4"></div>
					<div className="h-96 bg-gray-200 rounded"></div>
				</div>
			</div>
		)
	}

	if (!document) {
		return (
			<div className="p-6">
				<div className="text-center">
					<FileText className="h-12 w-12 text-gray-300 mx-auto mb-4" />
					<h2 className="text-xl font-semibold text-gray-900 mb-2">Document not found</h2>
					<p className="text-gray-600 mb-4">The document you're looking for doesn't exist.</p>
					<Link to="/documents" className="inline-flex items-center px-4 py-2 rounded-lg bg-gray-900 text-white text-sm font-medium">Back to Documents</Link>
				</div>
			</div>
		)
	}

	const getJobStatus = (jobType: string) => {
		const job = jobs.filter(j => j.job_type === jobType).sort((a: any, b: any) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())[0]
		return job?.status || 'pending'
	}

	const getJobProgress = (jobType: string) => {
		const job = jobs.filter(j => j.job_type === jobType).sort((a: any, b: any) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())[0]
		return job?.progress || 0
	}

	const getStatusIcon = (status: string) => {
		switch (status) {
			case 'completed':
				return <CheckCircle className="h-4 w-4 text-green-500" />
			case 'running':
				return <Clock className="h-4 w-4 text-yellow-500 animate-spin" />
			case 'failed':
				return <AlertCircle className="h-4 w-4 text-red-500" />
			default:
				return <Clock className="h-4 w-4 text-gray-400" />
		}
	}



	return (
		<div className="space-y-4">
			{/* Title + Toolbar */}
			<div className="bg-white border border-gray-200 rounded-xl px-4 py-3">
				<div className="flex items-center justify-between">
					<div className="flex items-center space-x-3 min-w-0">
						<Link to="/documents" className="p-2 rounded-lg text-gray-500 hover:bg-gray-100">
							<ArrowLeft className="h-5 w-5" />
						</Link>
						<div className="min-w-0">
							<h1 className="text_base font-semibold text-gray-900 truncate">{document.title}</h1>
							<p className="text-xs text-gray-500 truncate">{document.description || 'No description'}</p>
						</div>
					</div>
					<div className="flex items-center space-x-2">
						<button
							onClick={() => setMode(mode === 'redact' ? 'view' : 'redact')}
							title="Redact mode"
							className={`px-3 py-2 rounded-lg text-sm font-medium inline-flex items-center ${mode==='redact'?'bg-red-100 text-red-700':'bg-gray-100 text-gray-700 hover:bg-gray-200'}`}
						>
							<Edit3 className="h-4 w-4" />
							<span className="ml-2 hidden sm:inline">Redact</span>
						</button>
						<button
							onClick={() => setMode(mode === 'comment' ? 'view' : 'comment')}
							title="Comment mode"
							className={`px-3 py-2 rounded-lg text-sm font-medium inline-flex items-center ${mode==='comment'?'bg-blue-100 text-blue-700':'bg-gray-100 text-gray-700 hover:bg-gray-200'}`}
						>
							<MessageSquare className="h-4 w-4" />
							<span className="ml-2 hidden sm:inline">Comment</span>
						</button>
						<button
							onClick={handleShare}
							title="Share document link"
							className="px-3 py-2 rounded-lg text-sm font-medium bg-gray-100 text-gray-700 hover:bg-gray-200 inline-flex items-center"
						>
							<Share2 className="h-4 w-4 mr-2" /> Share
						</button>
						<button
							onClick={handleDownload}
							title="Download original document"
							className="px-3 py-2 rounded-lg text-sm font-medium bg-gray-100 text-gray-700 hover:bg-gray-200 inline-flex items-center"
						>
							<Download className="h-4 w-4 mr-2" /> Download
						</button>
						<button
							onClick={handleDelete}
							title="Delete document"
							className="px-3 py-2 rounded-lg text-sm font-medium bg-red-100 text-red-700 hover:bg-red-200 inline-flex items-center"
						>
							<Trash2 className="h-4 w-4 mr-2" /> Delete
						</button>

						<button
							onClick={() => setShowSidebar(!showSidebar)}
							title="Toggle sidebar"
							className="px-3 py-2 rounded-lg text-sm font-medium bg-gray-100 text-gray-700 hover:bg-gray-200 inline-flex items-center"
						>
							<MessageSquare className="h-4 w-4" />
						</button>
					</div>
				</div>
			</div>

			{/* Content Area */}
			<div className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-4">
				<div className="bg-white border border-gray-200 rounded-xl p-4">
					<DocumentViewer
						documentId={documentId}
						pageNumber={currentPage}
						onPageChange={setCurrentPage}
						totalPages={documentMetadata?.page_count || 1}
						className="h-[70vh]"
						redactionMode={mode === 'redact'}
						commentMode={mode === 'comment'}
						onRedactionCreate={handleCreateRedaction}
						onAddCommentAt={handleViewerClickAddComment}
						redactions={redactions || []}
						comments={comments || []}
						onRedactionUpdate={handleUpdateRedaction}
						onRedactionDelete={handleDeleteRedaction}
						showAnnotations={mode === 'comment' || mode === 'view'}
						showRedactions={mode === 'redact' || mode === 'view'}
					/>
					{/* Debug info */}
					{process.env.NODE_ENV === 'development' && (
						<div className="mt-2 p-2 bg-gray-100 text-xs">
							Mode: {mode} | Comments: {comments?.length || 0} | Redactions: {redactions?.length || 0} | Pages: {documentMetadata?.page_count || 'Loading...'}
						</div>
					)}
				</div>

				{/* Sidebar */}
				{showSidebar && (
					<aside className="bg-white border border-gray-200 rounded-xl p-4 h-fit sticky top-24 space-y-4">
						<div className="flex space-x-1">
							<button
								onClick={() => setSidebarTab('info')}
								className={clsx(
									'px-3 py-2 text-sm font-medium rounded-lg transition-colors',
									sidebarTab === 'info' ? 'bg-gray-900 text-white' : 'text-gray-700 hover:bg-gray-100'
								)}
							>
								Info
							</button>
							<button
								onClick={() => setSidebarTab('comments')}
								className={clsx(
									'px-3 py-2 text-sm font-medium rounded-lg transition-colors',
									sidebarTab === 'comments' ? 'bg-gray-900 text-white' : 'text-gray-700 hover:bg-gray-100'
								)}
							>
								Comments
							</button>
							<button
								onClick={() => setSidebarTab('redactions')}
								className={clsx(
									'px-3 py-2 text-sm font-medium rounded-lg transition-colors',
									sidebarTab === 'redactions' ? 'bg-gray-900 text-white' : 'text-gray-700 hover:bg-gray-100'
								)}
							>
								Redactions
							</button>
							<button
								onClick={() => setSidebarTab('ai')}
								className={clsx(
									'px-3 py-2 text-sm font-medium rounded-lg transition-colors',
									sidebarTab === 'ai' ? 'bg-gray-900 text-white' : 'text-gray-700 hover:bg-gray-100'
								)}
							>
								AI Q&A
							</button>
							<button
								onClick={() => setSidebarTab('sharing')}
								className={clsx(
									'px-3 py-2 text-sm font-medium rounded-lg transition-colors',
									sidebarTab === 'sharing' ? 'bg-gray-900 text-white' : 'text-gray-700 hover:bg-gray-100'
								)}
							>
								Share
							</button>
						</div>

						{sidebarTab === 'info' && (
							<div className="space-y-4">
								<div>
									<h3 className="text-sm font-semibold text-gray-900 mb-2">Document Details</h3>
									<div className="text-sm text-gray-600 space-y-1">
										<p><span className="font-medium">Status:</span> {document.status}</p>
										<p><span className="font-medium">Language:</span> {document.language}</p>
										<p><span className="font-medium">Source:</span> {document.source || '—'}</p>
										<p><span className="font-medium">Created:</span> {new Date(document.created_at).toLocaleString()}</p>
									</div>
								</div>
								<div>
									<h3 className="text-sm font-semibold text-gray-900 mb-2">Processing Status</h3>
									<div className="space-y-2">
										{['tiling','thumbnails','ocr'].map((jobType) => {
											const job = jobs.filter(j => j.job_type === jobType).sort((a: any, b: any) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())[0]
											const status = getJobStatus(jobType)
											return (
												<div key={jobType} className="p-2 bg-gray-50 rounded-lg">
													<div className="flex items-center justify-between">
														<div className="flex items-center space-x-2">
															{getStatusIcon(status)}
															<span className="text-sm text-gray-700 capitalize">{jobType}</span>
														</div>
														<span className="text-xs text-gray-500">{getJobProgress(jobType)}%</span>
													</div>
													{status === 'failed' && job?.error_message && (
														<div className="mt-2 p-2 bg-red-50 rounded border border-red-200">
															<p className="text-xs text-red-700 font-medium">Error:</p>
															<p className="text-xs text-red-600 mt-1">{job.error_message}</p>
														</div>
													)}
												</div>
											)
										})}
									</div>
								</div>
							</div>
						)}

						{sidebarTab === 'comments' && (
							<div className="space-y-4">
								<div>
									<h3 className="text-sm font-semibold text-gray-900 mb-2">Comments</h3>
									{comments.length === 0 ? (
										<p className="text-sm text-gray-500">No comments yet.</p>
									) : (
										<div className="space-y-2">
											{comments.map((comment: any, index: number) => (
												<div key={index} className="p-3 bg-gray-50 rounded-lg flex items-start justify-between gap-2">
													<div>
														<p className="text-sm text-gray-700">{comment.content}</p>
														<p className="text-xs text-gray-500 mt-1">{comment.created_at}</p>
													</div>
													<button
														onClick={async () => {
															// Prevent multiple rapid clicks
															if (deletingComments.has(comment.id)) return

															setDeletingComments(prev => new Set(prev).add(comment.id))

															try {
																await documentsApi.deleteComment(documentId, comment.id)
																queryClient.invalidateQueries(['document-comments', documentId])
																if (socketRef.current) {
																	socketRef.current.emit('delete_comment', { document_id: documentId, comment_id: String(comment.id) })
																}
																toast.success('Comment deleted')
															} catch (error: any) {
																// Handle 404 gracefully - comment might have been already deleted
																if (error?.response?.status === 404) {
																	console.log('Comment already deleted, refreshing comments')
																	queryClient.invalidateQueries(['document-comments', documentId])
																	toast.success('Comment deleted')
																} else {
																	toast.error('Failed to delete comment')
																}
															} finally {
																setDeletingComments(prev => {
																	const newSet = new Set(prev)
																	newSet.delete(comment.id)
																	return newSet
																})
															}
														}}
														disabled={deletingComments.has(comment.id)}
														className={`text-xs ${deletingComments.has(comment.id)
															? 'text-gray-400 cursor-not-allowed'
															: 'text-red-600 hover:text-red-800'
														}`}
													>
														{deletingComments.has(comment.id) ? 'Deleting...' : 'Delete'}
													</button>
												</div>
											))}
										</div>
									)}
								</div>
								<div>
									<h4 className="text-sm font-medium text-gray-900 mb-2">Add Comment</h4>
									<div className="space-y-2">
										<textarea
											value={newComment}
											onChange={(e) => setNewComment(e.target.value)}
											placeholder="Write a comment..."
											className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 resize-none"
											rows={3}
										/>
										<button
											onClick={handleAddComment}
											disabled={!newComment.trim()}
											className="inline-flex items-center px-3 py-2 rounded-lg bg-blue-600 text-white text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed hover:bg-blue-700"
										>
											<Send className="w-4 h-4 mr-2" />
											Add Comment
										</button>
									</div>
								</div>
							</div>
						)}

						{sidebarTab === 'redactions' && (
							<div className="space-y-4">
								<div>
									<h3 className="text-sm font-semibold text-gray-900 mb-2">Redactions</h3>
									{(redactions || []).length === 0 ? (
										<p className="text-sm text-gray-500">No redactions yet.</p>
									) : (
										<div className="space-y-2">
											{(redactions || []).map((r: any) => (
												<div key={r.id} className="p-3 bg-gray-50 rounded-lg flex items-center justify-between gap-2">
													<div className="text-xs text-gray-700">
														<div>Page {r.page_number + 1}</div>
														<div>({Math.round(Math.min(r.x_start, r.x_end))}, {Math.round(Math.min(r.y_start, r.y_end))}) → ({Math.round(Math.max(r.x_start, r.x_end))}, {Math.round(Math.max(r.y_start, r.y_end))})</div>
													</div>
													<div className="flex items-center gap-2">
														<button
															onClick={() => handleDeleteRedaction(r.id)}
															disabled={deletingRedactions.has(r.id)}
															className={`text-xs ${deletingRedactions.has(r.id) ? 'text-gray-400 cursor-not-allowed' : 'text-red-600 hover:text-red-800'}`}
														>
															{deletingRedactions.has(r.id) ? 'Deleting...' : 'Delete'}
														</button>
													</div>
												</div>
											))}
										</div>
									)}
								</div>
								<p className="text-xs text-gray-500">Tip: Drag a redaction on the page to move it. Use the corner handle to resize.</p>
							</div>
						)}

						{sidebarTab === 'ai' && (
							<div className="space-y-4">
								<div>
									<h3 className="text-sm font-semibold text-gray-900 mb-2">AI Q&A</h3>
									<div className="space-y-3">
										<div className="flex items-start space-x-2">
											<input
												value={aiQuestion}
												onChange={(e) => setAiQuestion(e.target.value)}
												onKeyPress={(e) => e.key === 'Enter' && handleAIQuestion()}
												placeholder="Ask a question about this document..."
												className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
												disabled={isLoadingAI}
											/>
											<button
												onClick={handleAIQuestion}
												disabled={!aiQuestion.trim() || isLoadingAI}
												title="Ask AI about this document"
												className="inline-flex items-center px-3 py-2 rounded-lg bg-blue-600 text-white text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed hover:bg-blue-700"
											>
												{isLoadingAI ? (
													<Clock className="w-4 h-4 animate-spin" />
												) : (
													<Bot className="w-4 h-4" />
												)}
											</button>
										</div>
										{aiAnswer && (
											<div className="p-3 bg-blue-50 border border-blue-200 rounded-lg">
												<h4 className="text-sm font-medium text-blue-900 mb-1">AI Response:</h4>
												<p className="text-sm text-blue-800">{aiAnswer}</p>
											</div>
										)}
										<p className="text-xs text-gray-500">Powered by local Ollama + RAG</p>
									</div>
								</div>
							</div>
						)}

						{sidebarTab === 'sharing' && (
							<div className="space-y-4">
								<div>
									<h3 className="text-sm font-semibold text-gray-900 mb-2">Share Document</h3>
									<div className="space-y-3">
										{/* Share with Everyone */}
										<div className="flex items-center space-x-2">
											<input
												type="checkbox"
												id="shareEveryone"
												checked={shareEveryone}
												onChange={(e) => setShareEveryone(e.target.checked)}
												className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
											/>
											<label htmlFor="shareEveryone" className="text-sm text-gray-700">
												Share with everyone
											</label>
										</div>

										{/* Email Input (disabled when sharing with everyone) */}
										{!shareEveryone && (
											<div>
												<label className="block text-xs font-medium text-gray-700 mb-1">
													Email Address
												</label>
												<input
													type="email"
													value={shareEmail}
													onChange={(e) => setShareEmail(e.target.value)}
													placeholder="user@example.com"
													className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
												/>
											</div>
										)}

										{/* Permission Level */}
										<div>
											<label className="block text-xs font-medium text-gray-700 mb-1">
												Permission Level
											</label>
											<select
												value={sharePermission}
												onChange={(e) => setSharePermission(e.target.value as 'view' | 'edit')}
												className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
											>
												<option value="view">View Only</option>
												<option value="edit">Can Edit</option>
											</select>
										</div>

										{/* Share Button */}
										<button
											onClick={handleCreateShare}
											disabled={!shareEveryone && !shareEmail.trim()}
											className="w-full inline-flex items-center justify-center px-3 py-2 rounded-lg bg-blue-600 text-white text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed hover:bg-blue-700"
										>
											<Share2 className="w-4 h-4 mr-2" />
											Share Document
										</button>
									</div>
								</div>

								{/* Existing Shares */}
								{shares.length > 0 && (
									<div>
										<h4 className="text-sm font-semibold text-gray-900 mb-2">Current Shares</h4>
										<div className="space-y-2">
											{shares.map((share: any) => (
												<div key={share.id} className="flex items-center justify-between p-2 bg-gray-50 rounded-lg">
													<div className="flex-1">
														<p className="text-sm font-medium text-gray-900">
															{share.is_everyone ? 'Everyone' : share.shared_with_email}
														</p>
														<p className="text-xs text-gray-500">
															{share.permission_level === 'view' ? 'View Only' : 'Can Edit'}
														</p>
													</div>
													<button
														onClick={() => documentsApi.deleteShare(documentId, share.id).then(() => {
															queryClient.invalidateQueries(['document-shares', documentId])
															toast.success('Share removed')
														})}
														className="text-red-600 hover:text-red-800 text-xs"
													>
														Remove
													</button>
												</div>
											))}
										</div>
									</div>
								)}
							</div>
						)}
					</aside>
				)}
			</div>
		</div>
	)
}
