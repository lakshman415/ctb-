/**
 * App shell — collapsible sidebar with grouped navigation + top bar.
 *
 * Design decisions:
 * - Grouped nav (Discover / Analyze / Track) scales to 10+ items without becoming a wall
 * - Collapsible sidebar reclaims 180px for data-dense tables
 * - Icons over emojis: consistent rendering, cleaner at small sizes
 * - Sidebar state persists (traders keep their preferred layout)
 */

import { type ReactNode, useEffect, useState } from 'react'
import { useTheme } from '../hooks/useTheme'
import { getTriggeredAlerts } from '../services/api'
import { Icons } from './ui/Icon'

interface LayoutProps {
  children: ReactNode
  currentPage: string
  onNavigate: (page: string) => void
}

interface NavItem {
  id: string
  label: string
  icon: (p: { size?: number; className?: string }) => ReactNode
  badge?: string
}

const NAV_GROUPS: { label: string; items: NavItem[] }[] = [
  {
    label: 'Discover',
    items: [
      { id: 'trending', label: 'Trending', icon: Icons.Flame },
      { id: 'scanner', label: 'Scanner', icon: Icons.Radar },
    ],
  },
  {
    label: 'Analyze',
    items: [
      { id: 'home', label: 'Token Analysis', icon: Icons.Search },
    ],
  },
  {
    label: 'Track',
    items: [
      { id: 'watchlist', label: 'Watchlist', icon: Icons.Star },
      { id: 'journal', label: 'Journal', icon: Icons.Book },
    ],
  },
]

const SIDEBAR_KEY = 'ctb-sidebar-collapsed'

export function Layout({ children, currentPage, onNavigate }: LayoutProps) {
  const { isDark, toggle } = useTheme()
  const [collapsed, setCollapsed] = useState(
    () => localStorage.getItem(SIDEBAR_KEY) === 'true'
  )
  const [alertCount, setAlertCount] = useState(0)

  // Poll for triggered alerts every 30s
  useEffect(() => {
    const check = async () => {
      try {
        const alerts = await getTriggeredAlerts()
        setAlertCount(alerts.length)
      } catch { /* silent */ }
    }
    check()
    const id = window.setInterval(check, 30_000)
    return () => clearInterval(id)
  }, [])

  const toggleSidebar = () => {
    const next = !collapsed
    setCollapsed(next)
    localStorage.setItem(SIDEBAR_KEY, String(next))
  }

  const allItems = NAV_GROUPS.flatMap(g => g.items)
  const activeItem = allItems.find(i => i.id === currentPage)

  return (
    <div className="flex h-screen overflow-hidden bg-surface-subtle dark:bg-surface-dark-base">
      {/* ═══ SIDEBAR ═══ */}
      <aside
        className={`shrink-0 flex flex-col border-r border-edge-light dark:border-edge-dark
                    bg-surface-base dark:bg-surface-dark-raised
                    transition-[width] duration-200 ease-out
                    ${collapsed ? 'w-14' : 'w-[200px]'}`}
      >
        {/* Logo */}
        <div className={`h-14 shrink-0 flex items-center gap-2.5 border-b border-edge-light dark:border-edge-dark
                        ${collapsed ? 'justify-center px-0' : 'px-4'}`}>
          <div className="w-7 h-7 shrink-0 rounded-md bg-gradient-to-br from-brand-400 to-brand-600
                          flex items-center justify-center shadow-sm">
            <span className="text-white text-xs font-bold tracking-tight">C</span>
          </div>
          {!collapsed && (
            <div className="min-w-0">
              <div className="text-sm font-semibold tracking-tight text-slate-900 dark:text-white leading-none">
                CTB
              </div>
              <div className="text-2xs text-slate-500 dark:text-slate-500 leading-none mt-0.5">
                Terminal
              </div>
            </div>
          )}
        </div>

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto py-3 px-2 space-y-4">
          {NAV_GROUPS.map((group) => (
            <div key={group.label}>
              {!collapsed && (
                <div className="px-2 mb-1.5 text-2xs font-semibold uppercase tracking-wider
                                text-slate-400 dark:text-slate-500">
                  {group.label}
                </div>
              )}
              <div className="space-y-0.5">
                {group.items.map((item) => {
                  const active = currentPage === item.id
                  const IconComp = item.icon
                  return (
                    <button
                      key={item.id}
                      onClick={() => onNavigate(item.id)}
                      title={collapsed ? item.label : undefined}
                      aria-current={active ? 'page' : undefined}
                      className={`w-full flex items-center gap-2.5 rounded-md
                                  transition-colors duration-150 group relative
                                  ${collapsed ? 'justify-center h-9 px-0' : 'h-8 px-2'}
                                  ${active
                                    ? 'bg-brand-50 dark:bg-brand-500/12 text-brand-700 dark:text-brand-300'
                                    : 'text-slate-600 dark:text-slate-400 hover:bg-surface-muted dark:hover:bg-surface-dark-hover hover:text-slate-900 dark:hover:text-slate-200'
                                  }`}
                    >
                      {active && !collapsed && (
                        <span className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-4 rounded-r bg-brand-500" />
                      )}
                      <span className="relative shrink-0">
                        <IconComp size={16} />
                        {item.id === 'watchlist' && alertCount > 0 && collapsed && (
                          <span className="absolute -top-1 -right-1 w-2 h-2 rounded-full bg-warning-500 ring-2 ring-surface-base dark:ring-surface-dark-raised" />
                        )}
                      </span>
                      {!collapsed && (
                        <>
                          <span className="text-xs font-medium truncate">{item.label}</span>
                          {item.id === 'watchlist' && alertCount > 0 && (
                            <span className="ml-auto px-1.5 h-4 rounded-full bg-warning-500 text-white
                                             text-[10px] font-bold inline-flex items-center tabular">
                              {alertCount}
                            </span>
                          )}
                        </>
                      )}
                    </button>
                  )
                })}
              </div>
            </div>
          ))}
        </nav>

        {/* Footer: collapse + theme */}
        <div className="shrink-0 border-t border-edge-light dark:border-edge-dark p-2 space-y-0.5">
          <button
            onClick={toggle}
            title={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
            className={`w-full flex items-center gap-2.5 h-8 rounded-md
                        text-slate-600 dark:text-slate-400
                        hover:bg-surface-muted dark:hover:bg-surface-dark-hover
                        hover:text-slate-900 dark:hover:text-slate-200
                        transition-colors duration-150
                        ${collapsed ? 'justify-center px-0' : 'px-2'}`}
          >
            {isDark ? <Icons.Moon size={16} /> : <Icons.Sun size={16} />}
            {!collapsed && <span className="text-xs font-medium">{isDark ? 'Dark' : 'Light'}</span>}
          </button>
          <button
            onClick={toggleSidebar}
            title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            className={`w-full flex items-center gap-2.5 h-8 rounded-md
                        text-slate-500 dark:text-slate-500
                        hover:bg-surface-muted dark:hover:bg-surface-dark-hover
                        hover:text-slate-800 dark:hover:text-slate-300
                        transition-colors duration-150
                        ${collapsed ? 'justify-center px-0' : 'px-2'}`}
          >
            <Icons.ChevronsLeft
              size={16}
              className={`transition-transform duration-200 ${collapsed ? 'rotate-180' : ''}`}
            />
            {!collapsed && <span className="text-xs font-medium">Collapse</span>}
          </button>
        </div>
      </aside>

      {/* ═══ MAIN ═══ */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top bar */}
        <header className="h-14 shrink-0 flex items-center justify-between gap-4 px-5
                           border-b border-edge-light dark:border-edge-dark
                           bg-surface-base dark:bg-surface-dark-raised">
          <div className="flex items-center gap-2 min-w-0">
            {activeItem && <activeItem.icon size={16} className="text-slate-400 dark:text-slate-500 shrink-0" />}
            <h1 className="text-base font-semibold tracking-tight text-slate-900 dark:text-white truncate">
              {activeItem?.label ?? 'Dashboard'}
            </h1>
          </div>

          <div className="flex items-center gap-3 shrink-0">
            <div className="flex items-center gap-1.5 px-2 py-1 rounded-md
                            bg-success-50 dark:bg-success-500/10">
              <span className="w-1.5 h-1.5 rounded-full bg-success-500 animate-pulse-dot" />
              <span className="text-2xs font-medium text-success-700 dark:text-success-400">Live</span>
            </div>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-hidden">{children}</main>
      </div>
    </div>
  )
}
