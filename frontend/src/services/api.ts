import axios from 'axios'

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
  getJobs: (id: number) => axios.get<ProcessingJob[]>(`/api/documents/${id}/jobs`),
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
