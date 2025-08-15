import React, { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
	ArrowLeft,
	FileText,
	MessageSquare,
	Download,
	Share2,
	Clock,
	CheckCircle,
	AlertCircle,
	Bot
} from 'lucide-react'
import { documentsApi } from '../services/api'
import DocumentViewer from '../components/DocumentViewer'
import { clsx } from 'clsx'

export default function DocumentViewerPage() {
	const { id } = useParams<{ id: string }>()
	const documentId = parseInt(id || '0')
	const [currentPage, setCurrentPage] = useState(0)
	const [showSidebar, setShowSidebar] = useState(true)
	const [sidebarTab, setSidebarTab] = useState<'info' | 'comments' | 'ai'>('info')
	const [aiQuestion, setAiQuestion] = useState('')

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

	const handleAskQuestion = () => {
		if (!aiQuestion.trim()) return
		// TODO: Integrate /search/ask endpoint
		setAiQuestion('')
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
							<h1 className="text-base font-semibold text-gray-900 truncate">{document.title}</h1>
							<p className="text-xs text-gray-500 truncate">{document.description || 'No description'}</p>
						</div>
					</div>
					<div className="flex items-center space-x-2">
						<button className="px-3 py-2 rounded-lg text-sm font-medium bg-gray-100 text-gray-700 hover:bg-gray-200 inline-flex items-center">
							<Share2 className="h-4 w-4 mr-2" /> Share
						</button>
						<button className="px-3 py-2 rounded-lg text-sm font-medium bg-gray-100 text-gray-700 hover:bg-gray-200 inline-flex items-center">
							<Download className="h-4 w-4 mr-2" /> Download
						</button>
						<button onClick={() => setShowSidebar(!showSidebar)} className="px-3 py-2 rounded-lg text-sm font-medium bg-gray-100 text-gray-700 hover:bg-gray-200 inline-flex items-center">
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
							<div>
								<p className="text-sm text-gray-600">Comments coming soon.</p>
							</div>
						)}

						{sidebarTab === 'ai' && (
							<div className="space-y-3">
								<div className="flex items-center space-x-2">
									<input
										value={aiQuestion}
										onChange={(e) => setAiQuestion(e.target.value)}
										placeholder="Ask a question about this document"
										className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
									/>
									<button onClick={handleAskQuestion} className="inline-flex items-center px-3 py-2 rounded-lg bg-gray-900 text-white text-sm font-medium">
										<Bot className="w-4 h-4 mr-2" />
										Ask
									</button>
								</div>
								<p className="text-xs text-gray-500">Powered by local Ollama + RAG</p>
							</div>
						)}
					</aside>
				)}
			</div>
		</div>
	)
}
