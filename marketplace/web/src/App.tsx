import { BrowserRouter, Routes, Route, Link } from 'react-router-dom'
import { AppWalletProvider } from './wallet'
import { Header, Footer } from './components/Shell'
import { MarketplacePage } from './pages/MarketplacePage'
import { ListingPage } from './pages/ListingPage'
import { WalletPage } from './pages/WalletPage'
import { VendorsPage } from './pages/VendorsPage'
import { VendorPage } from './pages/VendorPage'
import { HistoryPage } from './pages/HistoryPage'
import { ExplorerPage } from './pages/ExplorerPage'
import { BlockPage } from './pages/BlockPage'
import { TxPage } from './pages/TxPage'

const NotFound = () => (
  <div className="page">
    <h1>Nothing at this address.</h1>
    <p style={{ marginTop: 16 }}>
      Go back to the <Link to="/">directory</Link>.
    </p>
  </div>
)

export function App() {
  return (
    <AppWalletProvider>
      <BrowserRouter>
        <div className="app">
          <Header />
          <main>
            <Routes>
              <Route path="/" element={<MarketplacePage />} />
              <Route path="/listing/:id" element={<ListingPage />} />
              <Route path="/vendors" element={<VendorsPage />} />
              <Route path="/vendors/:slug" element={<VendorPage />} />
              <Route path="/wallet" element={<WalletPage />} />
              <Route path="/history" element={<HistoryPage />} />
              <Route path="/explorer" element={<ExplorerPage />} />
              <Route path="/explorer/block/:round" element={<BlockPage />} />
              <Route path="/explorer/tx/:txid" element={<TxPage />} />
              <Route path="*" element={<NotFound />} />
            </Routes>
          </main>
          <Footer />
        </div>
      </BrowserRouter>
    </AppWalletProvider>
  )
}

export default App
