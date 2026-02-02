import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  Globe,
  Database,
  ListTodo,
  Key,
  Settings,
} from 'lucide-react'
import { cn } from '@/lib/utils'

const navItems = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/crawler', icon: Globe, label: 'Crawler Config' },
  { to: '/indexer', icon: Database, label: 'Indexer Config' },
  { to: '/jobs', icon: ListTodo, label: 'Jobs' },
  { to: '/auth', icon: Key, label: 'Auth Sessions' },
  { to: '/settings', icon: Settings, label: 'Settings' },
]

export function Sidebar() {
  return (
    <aside className="w-64 border-r bg-muted/40 p-4">
      <div className="mb-8">
        <h1 className="text-xl font-bold">Harmony Admin</h1>
        <p className="text-sm text-muted-foreground">Crawling System</p>
      </div>

      <nav className="space-y-1">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors',
                isActive
                  ? 'bg-primary text-primary-foreground'
                  : 'text-muted-foreground hover:bg-muted hover:text-foreground'
              )
            }
          >
            <item.icon className="h-4 w-4" />
            {item.label}
          </NavLink>
        ))}
      </nav>
    </aside>
  )
}
