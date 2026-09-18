import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'
import { getCurrentUser, login as loginRequest } from '../api/resources'
import type { CurrentUser } from '../api/types'

interface AuthState {
  user: CurrentUser | null
  loading: boolean
  login: (username: string, password: string) => Promise<CurrentUser>
  logout: () => void
}

const AuthContext = createContext<AuthState | null>(null)

function loadStoredUser(): CurrentUser | null {
  const raw = localStorage.getItem('bsa_user')
  if (!raw) return null
  try {
    return JSON.parse(raw) as CurrentUser
  } catch {
    return null
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<CurrentUser | null>(loadStoredUser)
  const [loading] = useState(false)

  const login = useCallback(async (username: string, password: string) => {
    const tokenResponse = await loginRequest(username, password)
    localStorage.setItem('bsa_access_token', tokenResponse.access_token)
    const me = await getCurrentUser()
    localStorage.setItem('bsa_user', JSON.stringify(me))
    setUser(me)
    return me
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem('bsa_access_token')
    localStorage.removeItem('bsa_user')
    setUser(null)
  }, [])

  const value = useMemo(() => ({ user, loading, login, logout }), [user, loading, login, logout])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
