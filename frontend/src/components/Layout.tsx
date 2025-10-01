import React from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import {
	FileText,
	Search,
	Settings,
	LogOut,
	Home,
	User
} from 'lucide-react'
import { useAuthStore } from '../services/auth'
import { clsx } from 'clsx'

interface LayoutProps {
	children: React.ReactNode
}

export default function Layout({ children }: LayoutProps) {
	const { user, logout } = useAuthStore()
	const location = useLocation()
	const navigate = useNavigate()

	const navigation = [
		{ name: 'Dashboard', href: '/dashboard', icon: Home },
		{ name: 'Documents', href: '/documents', icon: FileText },
		// Route "Search" to Documents page search until a dedicated page exists
		{ name: 'Search', href: '/documents', icon: Search },
	]

	if (user?.role === 'admin') {
		navigation.push({ name: 'Admin', href: '/admin', icon: Settings })
	}

	return (
		<div className="apple-inspired-bg min-h-screen">
			<header className="sticky top-0 z-40 backdrop-blur-md bg-white/70 border-b border-gray-200/60">
				<div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
					<div className="h-16 flex items-center justify-between">
						<div className="flex items-center space-x-3">
							<div className="w-9 h-9 bg-gradient-to-br from-blue-500 to-blue-600 rounded-2xl flex items-center justify-center shadow-md shadow-blue-500/20">
								<FileText className="w-4 h-4 text-white" />
							</div>
							<div>
								<h1 className="text-base font-bold apple-gradient-text leading-none">Haqnow Community</h1>
								<p className="text-[11px] text-gray-500 font-medium">Document Platform</p>
							</div>
						</div>

						<nav className="hidden md:flex items-center space-x-1">
							{navigation.map((item) => {
								const isActive = location.pathname === item.href
								return (
									<Link
										key={item.name}
										to={item.href}
										onClick={(e) => {
											e.preventDefault()
											navigate(item.href)
											// signal documents page to focus input (handled there)
											window.dispatchEvent(new Event('focus-docs-search'))
										}}
										className={clsx(
											'inline-flex items-center px-3 py-2 rounded-xl text-sm font-semibold transition-colors',
											isActive ? 'bg-gray-900 text-white' : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
										)}
									>
										<item.icon className={clsx('w-4 h-4 mr-2', isActive ? 'text-white' : 'text-gray-400')} />
										{item.name}
									</Link>
								)
							})}
						</nav>

						<div className="flex items-center space-x-3">
							<div className="hidden sm:flex items-center px-3 py-2 rounded-xl bg-gray-100 text-gray-700 text-sm font-medium">
								<User className="w-4 h-4 mr-2 text-gray-600" />
								<span className="truncate max-w-[160px]">{user?.full_name || user?.email?.split('@')[0]}</span>
							</div>
							<button
								onClick={logout}
								className="px-3 py-2 rounded-xl text-sm font-semibold text-gray-600 hover:bg-gray-100 hover:text-gray-900 transition-colors inline-flex items-center"
								title="Logout"
							>
								<LogOut className="w-4 h-4 mr-2" />
								Logout
							</button>
						</div>
					</div>
				</div>
			</header>

			<main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
				{children}
			</main>
		</div>
	)
}
