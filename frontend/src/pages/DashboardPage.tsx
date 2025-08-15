import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  FileText,
  Upload,
  Search,
  Clock,
  CheckCircle,
  TrendingUp,
  Users,
  Database,
  Home
} from 'lucide-react'
import { documentsApi } from '../services/api'
import { useAuthStore } from '../services/auth'
import { clsx } from 'clsx'

export default function DashboardPage() {
  const { user } = useAuthStore()

  const { data: documents = [], isLoading } = useQuery({
    queryKey: ['documents'],
    queryFn: () => documentsApi.list().then(res => res.data),
  })

  const recentDocuments = documents.slice(0, 5)
  const processingCount = documents.filter(doc => doc.status === 'processing').length
  const completedCount = documents.filter(doc => doc.status === 'completed').length

  const stats = [
    {
      name: 'Total Documents',
      value: documents.length.toString(),
      icon: Database,
      color: 'text-blue-600',
      bg: 'bg-blue-50',
    },
    {
      name: 'Processing',
      value: processingCount.toString(),
      icon: Clock,
      color: 'text-yellow-600',
      bg: 'bg-yellow-50',
    },
    {
      name: 'Completed',
      value: completedCount.toString(),
      icon: CheckCircle,
      color: 'text-green-600',
      bg: 'bg-green-50',
    },
    {
      name: 'This Month',
      value: documents.filter(doc => {
        const created = new Date(doc.created_at)
        const now = new Date()
        return created.getMonth() === now.getMonth() && created.getFullYear() === now.getFullYear()
      }).length.toString(),
      icon: TrendingUp,
      color: 'text-purple-600',
      bg: 'bg-purple-50',
    },
  ]

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Modern Header */}
      <div className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center space-x-4">
              <Home className="w-6 h-6 text-gray-600" />
              <div>
                <h1 className="text-xl font-semibold text-gray-900">Dashboard</h1>
                <p className="text-sm text-gray-500">Welcome back, {user?.full_name || user?.email?.split('@')[0]}</p>
              </div>
            </div>
            <Link
              to="/documents"
              className="inline-flex items-center px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg transition-colors"
            >
              <Upload className="w-4 h-4 mr-2" />
              Upload Documents
            </Link>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Stats Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          {stats.map((stat) => (
            <div
              key={stat.name}
              className="bg-white rounded-lg border border-gray-200 p-6 hover:shadow-md transition-shadow"
            >
              <div className="flex items-center justify-between">
                <div className={clsx('p-3 rounded-lg', stat.bg)}>
                  <stat.icon className={clsx('h-6 w-6', stat.color)} />
                </div>
                <div className="text-right">
                  <p className="text-2xl font-bold text-gray-900">
                    {stat.value}
                  </p>
                  <p className="text-sm text-gray-500">{stat.name}</p>
                </div>
              </div>
            </div>
          ))}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Recent Documents */}
          <div className="lg:col-span-2">
            <div className="bg-white rounded-lg border border-gray-200 p-6">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-lg font-semibold text-gray-900">Recent Documents</h2>
                <Link
                  to="/documents"
                  className="text-sm text-blue-600 hover:text-blue-700 font-medium"
                >
                  View all →
                </Link>
              </div>

              {isLoading ? (
                <div className="space-y-4">
                  {[...Array(3)].map((_, i) => (
                    <div key={i} className="animate-pulse flex items-center space-x-4 p-4">
                      <div className="w-12 h-12 bg-gray-200 rounded-lg"></div>
                      <div className="flex-1">
                        <div className="h-4 bg-gray-200 rounded w-3/4 mb-2"></div>
                        <div className="h-3 bg-gray-200 rounded w-1/2"></div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : recentDocuments.length > 0 ? (
                <div className="space-y-3">
                  {recentDocuments.map((doc) => (
                    <Link
                      key={doc.id}
                      to={`/documents/${doc.id}`}
                      className="block p-4 rounded-lg hover:bg-gray-50 transition-colors border border-gray-100"
                    >
                      <div className="flex items-center space-x-4">
                        <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
                          <FileText className="w-5 h-5 text-blue-600" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <h3 className="text-sm font-medium text-gray-900 truncate">{doc.title}</h3>
                          <p className="text-sm text-gray-500 truncate">
                            {doc.description || 'No description'}
                          </p>
                        </div>
                        <div className="flex items-center space-x-2">
                          <span className={clsx(
                            'inline-flex items-center px-2 py-1 rounded-full text-xs font-medium',
                            doc.status === 'completed' && 'bg-green-100 text-green-700',
                            doc.status === 'processing' && 'bg-yellow-100 text-yellow-700',
                            doc.status === 'new' && 'bg-blue-100 text-blue-700',
                            doc.status === 'failed' && 'bg-red-100 text-red-700'
                          )}>
                            {doc.status}
                          </span>
                          <span className="text-xs text-gray-400">
                            {new Date(doc.created_at).toLocaleDateString()}
                          </span>
                        </div>
                      </div>
                    </Link>
                  ))}
                </div>
              ) : (
                <div className="text-center py-12">
                  <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-4">
                    <FileText className="w-8 h-8 text-gray-400" />
                  </div>
                  <h3 className="text-lg font-medium text-gray-900 mb-2">No documents yet</h3>
                  <p className="text-gray-500 mb-6">Get started by uploading your first document.</p>
                  <Link
                    to="/documents"
                    className="inline-flex items-center px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg transition-colors"
                  >
                    <Upload className="w-4 h-4 mr-2" />
                    Upload Document
                  </Link>
                </div>
              )}
            </div>
          </div>

          {/* Sidebar */}
          <div className="space-y-6">
            {/* Quick Actions */}
            <div className="bg-white rounded-lg border border-gray-200 p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">Quick Actions</h2>
              <div className="space-y-3">
                <Link
                  to="/documents"
                  className="flex items-center w-full p-3 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg transition-colors"
                >
                  <Upload className="w-4 h-4 mr-3" />
                  Upload Document
                </Link>
                <Link
                  to="/search"
                  className="flex items-center w-full p-3 bg-gray-100 hover:bg-gray-200 text-gray-700 font-medium rounded-lg transition-colors"
                >
                  <Search className="w-4 h-4 mr-3" />
                  Search Documents
                </Link>
                {user?.role === 'admin' && (
                  <Link
                    to="/admin"
                    className="flex items-center w-full p-3 bg-purple-100 hover:bg-purple-200 text-purple-700 font-medium rounded-lg transition-colors"
                  >
                    <Users className="w-4 h-4 mr-3" />
                    Manage Users
                  </Link>
                )}
              </div>
            </div>

            {/* System Status */}
            <div className="bg-white rounded-lg border border-gray-200 p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">System Status</h2>
              <div className="space-y-3">
                <div className="flex items-center justify-between p-3 bg-green-50 rounded-lg">
                  <span className="text-sm font-medium text-gray-700">API Status</span>
                  <div className="flex items-center">
                    <CheckCircle className="w-4 h-4 text-green-500 mr-2" />
                    <span className="text-xs font-medium text-green-600">Online</span>
                  </div>
                </div>
                <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                  <span className="text-sm font-medium text-gray-700">Processing Queue</span>
                  <div className="flex items-center">
                    {processingCount > 0 ? (
                      <>
                        <Clock className="w-4 h-4 text-yellow-500 mr-2" />
                        <span className="text-xs font-medium text-yellow-600">{processingCount} jobs</span>
                      </>
                    ) : (
                      <>
                        <CheckCircle className="w-4 h-4 text-green-500 mr-2" />
                        <span className="text-xs font-medium text-green-600">Clear</span>
                      </>
                    )}
                  </div>
                </div>
                <div className="flex items-center justify-between p-3 bg-blue-50 rounded-lg">
                  <span className="text-sm font-medium text-gray-700">Storage</span>
                  <div className="flex items-center">
                    <CheckCircle className="w-4 h-4 text-green-500 mr-2" />
                    <span className="text-xs font-medium text-green-600">Available</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
