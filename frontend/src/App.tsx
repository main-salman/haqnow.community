import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from './services/auth'
import LoginPage from './pages/LoginPage'
import DashboardPage from './pages/DashboardPage'
import DocumentsPage from './pages/DocumentsPage'
import DocumentViewerPage from './pages/DocumentViewerPage'
import AdminPage from './pages/AdminPage'
import Layout from './components/Layout'

function App() {
  const { isAuthenticated, user } = useAuthStore()

  if (!isAuthenticated) {
    return (
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    )
  }

  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/documents" element={<DocumentsPage />} />
        <Route path="/search" element={<Navigate to="/documents" replace />} />
        <Route path="/documents/:id" element={<DocumentViewerPage />} />
        {(user?.role === 'admin' || user?.role === 'superuser') && (
          <Route path="/admin" element={<AdminPage />} />
        )}
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </Layout>
  )
}

export default App
