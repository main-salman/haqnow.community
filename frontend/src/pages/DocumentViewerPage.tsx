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
import DocumentViewer from '../components/DocumentViewer'
import { clsx } from 'clsx'
import toast from 'react-hot-toast'
import { io, Socket } from 'socket.io-client'

export default function DocumentViewerPage() {
	const { id } = useParams<{ id: string }>()
	const documentId = parseInt(id || '0')
	const queryClient = useQueryClient()
	const [currentPage, setCurrentPage] = useState(0)
	const [showSidebar, setShowSidebar] = useState(true)
	const [sidebarTab, setSidebarTab] = useState<'info' | 'comments' | 'ai' | 'sharing'>('info')
	const [aiQuestion, setAiQuestion] = useState('')
	const [newComment, setNewComment] = useState('')
	const [aiAnswer, setAiAnswer] = useState('')
	const [isLoadingAI, setIsLoadingAI] = useState(false)
	const [redactionMode, setRedactionMode] = useState(false)
	const [shareEmail, setShareEmail] = useState('')
	const [sharePermission, setSharePermission] = useState<'view' | 'edit'>('view')
	const [shareEveryone, setShareEveryone] = useState(false)
	const socketRef = useRef<Socket | null>(null)
	const markersLayerRef = useRef<HTMLDivElement | null>(null)
	const [liveComments, setLiveComments] = useState<any[]>([])

	const { data: document, isLoading } = useQuery({
		queryKey: ['document', documentId],
		queryFn: () => documentsApi.get(documentId).then(res => res.data),
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
		queryFn: () => documentsApi.getComments(documentId).then(res => res.data.comments || []),
		enabled: !!documentId,
	})

	const { data: shares = [] } = useQuery({
		queryKey: ['document-shares', documentId],
		queryFn: () => documentsApi.getShares(documentId).then(res => res.data),
		enabled: !!documentId,
	})

	// Handlers for functionality
	const handleDownload = async () => {
		try {
			const response = await documentsApi.download(documentId)
			toast.success('Download started')
			// In production, this would trigger actual file download
		} catch (error) {
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
			await documentsApi.addRedaction(documentId, redactionData)
			toast.success('Redaction added successfully')
			// Refresh redactions
			queryClient.invalidateQueries(['document-redactions', documentId])
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

	useEffect(() => {
		// connect to socket server
		const s = io('/socket.io', { path: '/socket.io', transports: ['websocket'] })
		socketRef.current = s
		s.on('connect', () => {
			s.emit('join_document', { document_id: documentId })
		})
		s.on('document_state', (state: any) => {
			if (state?.comments) setLiveComments(state.comments)
		})
		s.on('comment_added', (payload: any) => {
			setLiveComments((prev) => [...prev, payload.comment])
		})
		return () => {
			s.emit('leave_document', { document_id: documentId })
			s.disconnect()
		}
	}, [documentId])

	useEffect(() => {
		// render markers overlay (guard for SSR/slow mount)
		if (typeof document === 'undefined') return
		const container = document.querySelector('[data-testid="viewer-container"]') as HTMLDivElement | null
		if (!container) return
		// create layer if not exists
		if (!markersLayerRef.current) {
			const layer = document.createElement('div')
			layer.style.position = 'absolute'
			layer.style.inset = '0'
			layer.style.pointerEvents = 'none'
			container.appendChild(layer)
			markersLayerRef.current = layer
		}
		const layer = markersLayerRef.current!
		layer.innerHTML = ''
		liveComments.forEach((c) => {
			if (typeof c.x_position === 'number' && typeof c.y_position === 'number' && c.page_number === currentPage) {
				const dot = document.createElement('div')
				dot.title = c.content || 'Comment'
				dot.style.position = 'absolute'
				dot.style.width = '10px'
				dot.style.height = '10px'
				dot.style.borderRadius = '9999px'
				dot.style.background = '#2563eb'
				dot.style.boxShadow = '0 0 0 2px rgba(37,99,235,0.3)'
				// positions are normalized from viewer
				dot.style.left = `${c.x_position * 100}%`
				dot.style.top = `${c.y_position * 100}%`
				dot.style.transform = 'translate(-50%, -50%)'
				layer.appendChild(dot)
			}
		})
	}, [liveComments, currentPage])

	const handleViewerClickAddComment = (x: number, y: number, page: number) => {
		setNewComment((prev) => prev || 'New comment')
		handleAddComment(x, y, page)
		// emit live comment marker to others
		if (socketRef.current) {
			socketRef.current.emit('add_comment', {
				document_id: documentId,
				comment: { page_number: page, x_position: x, y_position: y, content: newComment || 'New comment' }
			})
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
		const job = jobs.find(j => j.job_type === jobType)
		return job?.status || 'pending'
	}

	const getJobProgress = (jobType: string) => {
		const job = jobs.find(j => j.job_type === jobType)
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
							onClick={() => setRedactionMode(!redactionMode)}
							title={redactionMode ? "Exit redaction mode" : "Enter redaction mode"}
							className={`px-3 py-2 rounded-lg text-sm font-medium inline-flex items-center ${
								redactionMode
									? 'bg-red-100 text-red-700 hover:bg-red-200'
									: 'bg-gray-100 text-gray-700 hover:bg-gray-200'
							}`}
						>
							<Edit3 className="h-4 w-4" />
							{redactionMode && <span className="ml-2">Exit Redact</span>}
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
						totalPages={3}
						className="h-[70vh]"
						redactionMode={redactionMode}
						onRedactionCreate={handleCreateRedaction}
						onAddCommentAt={handleViewerClickAddComment}
					/>
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
										{['tiling','thumbnails','ocr'].map((jobType) => (
											<div key={jobType} className="flex items-center justify-between p-2 bg-gray-50 rounded-lg">
												<div className="flex items-center space-x-2">
													{getStatusIcon(getJobStatus(jobType))}
													<span className="text-sm text-gray-700 capitalize">{jobType}</span>
												</div>
												<span className="text-xs text-gray-500">{getJobProgress(jobType)}%</span>
											</div>
										))}
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
												<div key={index} className="p-3 bg-gray-50 rounded-lg">
													<p className="text-sm text-gray-700">{comment.content}</p>
													<p className="text-xs text-gray-500 mt-1">{comment.created_at}</p>
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
