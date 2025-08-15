import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import {
  Users,
  Key,
  Plus,
  Trash2,
  Eye,
  EyeOff,
  Copy,
  CheckCircle,
  AlertCircle,
  Calendar,
  Shield
} from 'lucide-react'
import { adminApi, User, ApiKey } from '../services/api'
import { clsx } from 'clsx'
import toast from 'react-hot-toast'

const userSchema = z.object({
  email: z.string().email('Invalid email address'),
  full_name: z.string().optional(),
  role: z.enum(['admin', 'manager', 'contributor', 'viewer']),
  password: z.string().min(8, 'Password must be at least 8 characters'),
})

const apiKeySchema = z.object({
  name: z.string().min(1, 'Name is required'),
  scopes: z.string().min(1, 'Scopes are required'),
})

type UserForm = z.infer<typeof userSchema>
type ApiKeyForm = z.infer<typeof apiKeySchema>

export default function AdminPage() {
  const [activeTab, setActiveTab] = useState<'users' | 'api-keys'>('users')
  const [showCreateUser, setShowCreateUser] = useState(false)
  const [showCreateApiKey, setShowCreateApiKey] = useState(false)
  const [showPassword, setShowPassword] = useState(false)
  const [newApiKey, setNewApiKey] = useState<string | null>(null)

  const queryClient = useQueryClient()

  // Users queries and mutations
  const { data: users = [], isLoading: usersLoading } = useQuery({
    queryKey: ['admin-users'],
    queryFn: () => adminApi.listUsers().then(res => res.data),
  })

  const createUserMutation = useMutation({
    mutationFn: adminApi.createUser,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-users'] })
      setShowCreateUser(false)
      toast.success('User created successfully')
      resetUserForm()
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to create user')
    },
  })

  // API Keys queries and mutations
  const { data: apiKeys = [], isLoading: apiKeysLoading } = useQuery({
    queryKey: ['admin-api-keys'],
    queryFn: () => adminApi.listApiKeys().then(res => res.data),
  })

  const createApiKeyMutation = useMutation({
    mutationFn: adminApi.createApiKey,
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['admin-api-keys'] })
      setNewApiKey(data.data.api_key)
      setShowCreateApiKey(false)
      toast.success('API key created successfully')
      resetApiKeyForm()
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to create API key')
    },
  })

  const revokeApiKeyMutation = useMutation({
    mutationFn: adminApi.revokeApiKey,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-api-keys'] })
      toast.success('API key revoked successfully')
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to revoke API key')
    },
  })

  // Forms
  const {
    register: registerUser,
    handleSubmit: handleSubmitUser,
    formState: { errors: userErrors },
    reset: resetUserForm,
  } = useForm<UserForm>({
    resolver: zodResolver(userSchema),
  })

  const {
    register: registerApiKey,
    handleSubmit: handleSubmitApiKey,
    formState: { errors: apiKeyErrors },
    reset: resetApiKeyForm,
  } = useForm<ApiKeyForm>({
    resolver: zodResolver(apiKeySchema),
    defaultValues: {
      scopes: 'ingest,search,export',
    },
  })

  const onSubmitUser = (data: UserForm) => {
    createUserMutation.mutate(data)
  }

  const onSubmitApiKey = (data: ApiKeyForm) => {
    createApiKeyMutation.mutate(data)
  }

  const copyApiKey = (key: string) => {
    navigator.clipboard.writeText(key)
    toast.success('API key copied to clipboard')
  }

  const getRoleColor = (role: string) => {
    switch (role) {
      case 'admin':
        return 'bg-red-100 text-red-800'
      case 'manager':
        return 'bg-blue-100 text-blue-800'
      case 'contributor':
        return 'bg-green-100 text-green-800'
      case 'viewer':
        return 'bg-gray-100 text-gray-800'
      default:
        return 'bg-gray-100 text-gray-800'
    }
  }

  return (
    <div className="p-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">Admin Console</h1>
        <p className="text-gray-600">Manage users, API keys, and system settings</p>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200 mb-8">
        <nav className="-mb-px flex space-x-8">
          <button
            onClick={() => setActiveTab('users')}
            className={clsx(
              'py-2 px-1 border-b-2 font-medium text-sm transition-colors',
              activeTab === 'users'
                ? 'border-primary-500 text-primary-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            )}
          >
            <Users className="h-4 w-4 mr-2 inline" />
            Users
          </button>
          <button
            onClick={() => setActiveTab('api-keys')}
            className={clsx(
              'py-2 px-1 border-b-2 font-medium text-sm transition-colors',
              activeTab === 'api-keys'
                ? 'border-primary-500 text-primary-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            )}
          >
            <Key className="h-4 w-4 mr-2 inline" />
            API Keys
          </button>
        </nav>
      </div>

      {/* Users Tab */}
      {activeTab === 'users' && (
        <div className="space-y-6">
          <div className="flex justify-between items-center">
            <h2 className="text-xl font-semibold text-gray-900">User Management</h2>
            <button
              onClick={() => setShowCreateUser(true)}
              className="btn-primary"
            >
              <Plus className="h-4 w-4 mr-2" />
              Create User
            </button>
          </div>

          {/* Create User Modal */}
          {showCreateUser && (
            <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
              <div className="bg-white rounded-lg p-6 w-full max-w-md">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Create New User</h3>
                <form onSubmit={handleSubmitUser(onSubmitUser)} className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Email Address
                    </label>
                    <input
                      {...registerUser('email')}
                      type="email"
                      className={clsx('input w-full', userErrors.email && 'border-red-300')}
                      placeholder="user@example.com"
                    />
                    {userErrors.email && (
                      <p className="mt-1 text-sm text-red-600">{userErrors.email.message}</p>
                    )}
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Full Name (Optional)
                    </label>
                    <input
                      {...registerUser('full_name')}
                      type="text"
                      className="input w-full"
                      placeholder="John Doe"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Role
                    </label>
                    <select {...registerUser('role')} className="input w-full">
                      <option value="viewer">Viewer</option>
                      <option value="contributor">Contributor</option>
                      <option value="manager">Manager</option>
                      <option value="admin">Admin</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Password
                    </label>
                    <div className="relative">
                      <input
                        {...registerUser('password')}
                        type={showPassword ? 'text' : 'password'}
                        className={clsx('input w-full pr-10', userErrors.password && 'border-red-300')}
                        placeholder="Enter password"
                      />
                      <button
                        type="button"
                        onClick={() => setShowPassword(!showPassword)}
                        className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-400"
                      >
                        {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                      </button>
                    </div>
                    {userErrors.password && (
                      <p className="mt-1 text-sm text-red-600">{userErrors.password.message}</p>
                    )}
                  </div>

                  <div className="flex justify-end space-x-3 pt-4">
                    <button
                      type="button"
                      onClick={() => setShowCreateUser(false)}
                      className="btn-secondary"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      disabled={createUserMutation.isPending}
                      className="btn-primary"
                    >
                      {createUserMutation.isPending ? 'Creating...' : 'Create User'}
                    </button>
                  </div>
                </form>
              </div>
            </div>
          )}

          {/* Users List */}
          <div className="card">
            {usersLoading ? (
              <div className="space-y-4">
                {[...Array(3)].map((_, i) => (
                  <div key={i} className="animate-pulse flex items-center space-x-4">
                    <div className="h-10 w-10 bg-gray-200 rounded-full"></div>
                    <div className="flex-1">
                      <div className="h-4 bg-gray-200 rounded w-1/3 mb-2"></div>
                      <div className="h-3 bg-gray-200 rounded w-1/4"></div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="space-y-4">
                {users.map((user) => (
                  <div key={user.id} className="flex items-center justify-between p-4 border border-gray-200 rounded-lg">
                    <div className="flex items-center space-x-4">
                      <div className="h-10 w-10 bg-primary-100 rounded-full flex items-center justify-center">
                        <Users className="h-5 w-5 text-primary-600" />
                      </div>
                      <div>
                        <h3 className="font-medium text-gray-900">
                          {user.full_name || user.email}
                        </h3>
                        <p className="text-sm text-gray-500">{user.email}</p>
                      </div>
                    </div>
                    <div className="flex items-center space-x-3">
                      <span className={clsx(
                        'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium',
                        getRoleColor(user.role)
                      )}>
                        {user.role}
                      </span>
                      <div className="flex items-center">
                        {user.is_active ? (
                          <CheckCircle className="h-4 w-4 text-green-500" />
                        ) : (
                          <AlertCircle className="h-4 w-4 text-red-500" />
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* API Keys Tab */}
      {activeTab === 'api-keys' && (
        <div className="space-y-6">
          <div className="flex justify-between items-center">
            <h2 className="text-xl font-semibold text-gray-900">API Key Management</h2>
            <button
              onClick={() => setShowCreateApiKey(true)}
              className="btn-primary"
            >
              <Plus className="h-4 w-4 mr-2" />
              Create API Key
            </button>
          </div>

          {/* Create API Key Modal */}
          {showCreateApiKey && (
            <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
              <div className="bg-white rounded-lg p-6 w-full max-w-md">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Create New API Key</h3>
                <form onSubmit={handleSubmitApiKey(onSubmitApiKey)} className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Key Name
                    </label>
                    <input
                      {...registerApiKey('name')}
                      type="text"
                      className={clsx('input w-full', apiKeyErrors.name && 'border-red-300')}
                      placeholder="My API Key"
                    />
                    {apiKeyErrors.name && (
                      <p className="mt-1 text-sm text-red-600">{apiKeyErrors.name.message}</p>
                    )}
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Scopes
                    </label>
                    <input
                      {...registerApiKey('scopes')}
                      type="text"
                      className={clsx('input w-full', apiKeyErrors.scopes && 'border-red-300')}
                      placeholder="ingest,search,export,admin"
                    />
                    {apiKeyErrors.scopes && (
                      <p className="mt-1 text-sm text-red-600">{apiKeyErrors.scopes.message}</p>
                    )}
                    <p className="mt-1 text-xs text-gray-500">
                      Comma-separated list of scopes: ingest, search, export, admin
                    </p>
                  </div>

                  <div className="flex justify-end space-x-3 pt-4">
                    <button
                      type="button"
                      onClick={() => setShowCreateApiKey(false)}
                      className="btn-secondary"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      disabled={createApiKeyMutation.isPending}
                      className="btn-primary"
                    >
                      {createApiKeyMutation.isPending ? 'Creating...' : 'Create API Key'}
                    </button>
                  </div>
                </form>
              </div>
            </div>
          )}

          {/* New API Key Display */}
          {newApiKey && (
            <div className="card bg-green-50 border-green-200">
              <div className="flex items-start space-x-3">
                <CheckCircle className="h-5 w-5 text-green-500 mt-0.5" />
                <div className="flex-1">
                  <h3 className="font-medium text-green-900 mb-2">API Key Created Successfully</h3>
                  <p className="text-sm text-green-700 mb-3">
                    Please copy this API key now. You won't be able to see it again.
                  </p>
                  <div className="flex items-center space-x-2">
                    <code className="flex-1 p-2 bg-white border border-green-300 rounded text-sm font-mono">
                      {newApiKey}
                    </code>
                    <button
                      onClick={() => copyApiKey(newApiKey)}
                      className="btn-secondary p-2"
                      title="Copy to clipboard"
                    >
                      <Copy className="h-4 w-4" />
                    </button>
                  </div>
                </div>
                <button
                  onClick={() => setNewApiKey(null)}
                  className="text-green-400 hover:text-green-600"
                >
                  ×
                </button>
              </div>
            </div>
          )}

          {/* API Keys List */}
          <div className="card">
            {apiKeysLoading ? (
              <div className="space-y-4">
                {[...Array(3)].map((_, i) => (
                  <div key={i} className="animate-pulse flex items-center space-x-4">
                    <div className="h-10 w-10 bg-gray-200 rounded-full"></div>
                    <div className="flex-1">
                      <div className="h-4 bg-gray-200 rounded w-1/3 mb-2"></div>
                      <div className="h-3 bg-gray-200 rounded w-1/4"></div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="space-y-4">
                {apiKeys.map((apiKey) => (
                  <div key={apiKey.id} className="flex items-center justify-between p-4 border border-gray-200 rounded-lg">
                    <div className="flex items-center space-x-4">
                      <div className="h-10 w-10 bg-yellow-100 rounded-full flex items-center justify-center">
                        <Key className="h-5 w-5 text-yellow-600" />
                      </div>
                      <div>
                        <h3 className="font-medium text-gray-900">{apiKey.name}</h3>
                        <p className="text-sm text-gray-500">
                          Scopes: {apiKey.scopes} • Created {new Date(apiKey.created_at).toLocaleDateString()}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center space-x-3">
                      {apiKey.last_used_at && (
                        <span className="text-xs text-gray-500">
                          Last used: {new Date(apiKey.last_used_at).toLocaleDateString()}
                        </span>
                      )}
                      <button
                        onClick={() => revokeApiKeyMutation.mutate(apiKey.id)}
                        className="text-red-600 hover:text-red-800 p-1"
                        title="Revoke API key"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
