import { useState, type ReactNode } from 'react'
import { Sidebar } from './Sidebar'
import { Header } from './Header'
import { useAuth } from '../auth/AuthContext'
import { cn } from '../lib/utils'

export function Layout({ children }: { children: ReactNode }) {
  const { user } = useAuth()
  const [collapsed, setCollapsed] = useState(false)
  if (!user) return null

  return (
    <div className="min-h-screen bg-background">
      <Sidebar collapsed={collapsed} onToggle={() => setCollapsed((c) => !c)} />
      <div className={cn('flex min-h-screen flex-col transition-all duration-300', collapsed ? 'ml-[72px]' : 'ml-[240px]')}>
        <Header />
        <main className="flex-1 p-6">{children}</main>
      </div>
    </div>
  )
}
