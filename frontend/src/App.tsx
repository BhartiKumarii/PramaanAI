import { Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider, useAuth } from './auth/AuthContext'
import { Layout } from './components/Layout'
import { LandingPage } from './pages/LandingPage'
import { LoginPage } from './pages/LoginPage'
import { FeaturesPage } from './pages/FeaturesPage'
import { HowItWorksPage } from './pages/HowItWorksPage'
import { SecurityPage } from './pages/SecurityPage'
import { AboutPage } from './pages/AboutPage'
import { Dashboard } from './pages/Dashboard'
import { CasesList } from './pages/CasesList'
import { CaseReview } from './pages/CaseReview'
import { AdminUsers } from './pages/AdminUsers'
import { IdentityIntelligence } from './pages/IdentityIntelligence'
import { DeviceManagement } from './pages/DeviceManagement'
import { DocumentIntelligence } from './pages/DocumentIntelligence'
import { Officers } from './pages/Officers'
import { AreaMonitoring } from './pages/AreaMonitoring'
import { Reports } from './pages/Reports'
import { Settings } from './pages/Settings'
import { AuditLogs } from './pages/AuditLogs'
import { Checkpoints } from './pages/Checkpoints'

function AppRoutes() {
  const { user } = useAuth()

  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/features" element={<FeaturesPage />} />
      <Route path="/how-it-works" element={<HowItWorksPage />} />
      <Route path="/security" element={<SecurityPage />} />
      <Route path="/about" element={<AboutPage />} />
      <Route path="/login" element={user ? <Navigate to="/console" replace /> : <LoginPage />} />
      <Route
        path="/console/*"
        element={
          user ? (
            <Layout>
              <Routes>
                <Route path="/" element={<Dashboard />} />
                <Route path="/cases" element={<CasesList view="all" />} />
                <Route path="/cases/:caseId" element={<CaseReview />} />
                <Route path="/requests" element={<CasesList view="requests" />} />
                <Route path="/results" element={<CasesList view="results" />} />
                <Route path="/alerts" element={<CasesList view="alerts" />} />
                <Route path="/identity" element={<IdentityIntelligence />} />
                <Route path="/document-intelligence" element={<DocumentIntelligence />} />
                <Route path="/checkpoints" element={<Checkpoints />} />
                <Route path="/area-monitoring" element={<AreaMonitoring />} />
                <Route path="/officers" element={<Officers />} />
                <Route path="/devices" element={<DeviceManagement />} />
                <Route path="/admin/users" element={<AdminUsers />} />
                <Route path="/admin/audit-logs" element={<AuditLogs />} />
                <Route path="/analytics" element={<Reports />} />
                <Route path="/settings" element={<Settings />} />
                <Route path="*" element={<Navigate to="/console" replace />} />
              </Routes>
            </Layout>
          ) : (
            <Navigate to="/login" replace />
          )
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <AppRoutes />
    </AuthProvider>
  )
}
