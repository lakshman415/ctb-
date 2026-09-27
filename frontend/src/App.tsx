import { useState } from 'react'
import { Layout } from './components/Layout'
import { HomePage } from './pages/HomePage'
import { JournalPage } from './pages/JournalPage'
import { ScannerPage } from './pages/ScannerPage'
import { TrendingPage } from './pages/TrendingPage'
import { WatchlistPage } from './pages/WatchlistPage'

const PAGES: Record<string, () => JSX.Element> = {
  trending: TrendingPage,
  scanner: ScannerPage,
  home: HomePage,
  watchlist: WatchlistPage,
  journal: JournalPage,
}

export default function App() {
  const [page, setPage] = useState('trending')
  const Page = PAGES[page] ?? TrendingPage

  return (
    <Layout currentPage={page} onNavigate={setPage}>
      <Page />
    </Layout>
  )
}
