import axios from 'axios'
import { useAuthStore } from './auth'

export interface Document {
  id: number
  title: string
  description?: string
  source?: string
  language: string
  status: string
  uploader_id: number
  published_date?: string
  acquired_date?: string
  event_date?: string
  filing_date?: string
  created_at: string
  updated_at: string
}

// Inject auth token on every request and handle 401 globally
axios.interceptors.request.use((config) => {
  try {
    const token = useAuthStore.getState().token
    if (token) {
      config.headers = config.headers || {}
      ;(config.headers as any)['Authorization'] = `Bearer ${token}`
    }
  } catch {}
  return config
})

axios.interceptors.response.use(
  (resp) => resp,
  (error) => {
    if (error?.response?.status === 401) {
      const url: string = error?.config?.url || ''
      const isAuthFlow = url.includes('/api/auth/login') || url.includes('/api/auth/mfa') || url.includes('/api/auth/register')
      if (!isAuthFlow) {
        try { useAuthStore.getState().logout() } catch {}
        if (typeof window !== 'undefined') {
          window.location.href = '/login'
        }
      }
    }
    return Promise.reject(error)
  }
)

export interface ProcessingJob {
  id: number
  job_type: string
  status: string
  progress: number
  error_message?: string
  created_at: string
  started_at?: string
  completed_at?: string
}

export interface ApiKey {
  id: number
  name: string
  scopes: string
  created_by: number
  last_used_at?: string
  is_active: boolean
  created_at: string
}

export interface CreateApiKeyResponse {
  api_key: string
  key_info: ApiKey
}

export interface User {
  id: number
  email: string
  full_name?: string
  role: string
  is_active: boolean
}

export interface PresignedUploadResponse {
  upload_id: string
  upload_url: string
  fields: Record<string, string>
}

// Documents API
export const documentsApi = {
  list: () => axios.get<Document[]>('/api/documents/'),
  get: (id: number) => axios.get<Document>(`/api/documents/${id}`),
  create: (data: Partial<Document>) => axios.post<Document>('/api/documents/', data),
  delete: (id: number) => axios.delete(`/api/documents/${id}`),
  bulkUpload: (files: File[]) => {
    const formData = new FormData()
    files.forEach(file => formData.append('files', file))
    return axios.post('/api/documents/bulk-upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  },
  // Authored content documents
  createContent: (data: { title: string; markdown: string; references?: number[] }) =>
    axios.post('/api/documents/content', data),
  getJobs: (id: number) => axios.get<ProcessingJob[]>(`/api/documents/${id}/jobs`),
  getMetadata: (id: number) => axios.get<Document & { page_count: number }>(`/api/documents/${id}/metadata`),
  getPresignedUpload: (filename: string, contentType: string, size: number) =>
    axios.post<PresignedUploadResponse>('/api/documents/presigned-upload', {
      filename,
      content_type: contentType,
      size,
    }),
  download: (id: number) => axios.get(`/api/documents/${id}/download`),
  getComments: (id: number) => axios.get(`/api/documents/${id}/comments`),
  addComment: (id: number, commentData: any) =>
    axios.post(`/api/documents/${id}/comments`, commentData),
  updateComment: (id: number, commentId: number, updateData: any) =>
    axios.put(`/api/documents/${id}/comments/${commentId}`, updateData),
  deleteComment: (id: number, commentId: number) =>
    axios.delete(`/api/documents/${id}/comments/${commentId}`),
  export: (id: number, options: { format: string; pages?: number[] }) =>
    axios.post(`/api/documents/${id}/export`, options),

  // Sharing
  shareDocument: (id: number, shareData: {
    shared_with_email?: string;
    permission_level: 'view' | 'edit';
    is_everyone?: boolean;
    expires_at?: string;
  }) => axios.post(`/api/documents/${id}/shares`, shareData),
  getShares: (id: number) => axios.get(`/api/documents/${id}/shares`),
  updateShare: (id: number, shareId: number, updateData: {
    permission_level?: 'view' | 'edit';
    expires_at?: string;
  }) => axios.put(`/api/documents/${id}/shares/${shareId}`, updateData),
  deleteShare: (id: number, shareId: number) =>
    axios.delete(`/api/documents/${id}/shares/${shareId}`),
  checkAccess: (id: number) => axios.get(`/api/documents/${id}/access`),

  // Redactions
  addRedaction: (id: number, redactionData: {
    page_number: number;
    x_start: number;
    y_start: number;
    x_end: number;
    y_end: number;
    reason?: string;
  }) => axios.post(`/api/documents/${id}/redactions`, redactionData),
  getRedactions: (id: number) => axios.get(`/api/documents/${id}/redactions`),
  updateRedaction: (id: number, redactionId: number, update: Partial<{ x_start: number; y_start: number; x_end: number; y_end: number; reason: string }>) =>
    axios.put(`/api/documents/${id}/redactions/${redactionId}`, update),
  deleteRedaction: (id: number, redactionId: number) =>
    axios.delete(`/api/documents/${id}/redactions/${redactionId}`),
  // Apply/Remove page redactions (burn-in)
  applyPageRedactions: (id: number, pageNumber: number, regions: Array<{ x: number; y: number; width: number; height: number; color?: string }>) =>
    axios.post(`/api/documents/${id}/pages/${pageNumber}/redact`, { redactions: regions }),
  removePageRedactions: (id: number, pageNumber: number) =>
    axios.delete(`/api/documents/${id}/pages/${pageNumber}/redact`),
}

// Search API
export const searchApi = {
  search: (query: string) => axios.get(`/api/search/?q=${encodeURIComponent(query)}`),
  askQuestion: (documentId: number, question: string) =>
    axios.post('/api/search/ask', { document_id: documentId, question }),
}

// Admin API
export const adminApi = {
  // Users
  listUsers: () => axios.get<User[]>('/api/auth/admin/users'),
  createUser: (data: {
    email: string
    full_name?: string
    role: string
    password: string
  }) => axios.post<User>('/api/auth/admin/users', data),

  // API Keys
  listApiKeys: () => axios.get<ApiKey[]>('/api/auth/admin/api-keys'),
  createApiKey: (data: { name: string; scopes: string }) =>
    axios.post<CreateApiKeyResponse>('/api/auth/admin/api-keys', data),
  revokeApiKey: (id: number) => axios.delete(`/api/auth/admin/api-keys/${id}`),
}
