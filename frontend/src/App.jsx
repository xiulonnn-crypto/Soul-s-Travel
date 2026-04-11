import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Home from './pages/Home'
import TripList from './pages/TripList'
import TripDetail from './pages/TripDetail'
import TripEditor from './pages/TripEditor'
import ShareView from './pages/ShareView'

function Placeholder({ name }) {
  return <div style={{ padding: 40, fontSize: 20, color: '#8e99a4' }}>{name} - Coming Soon</div>
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/share/:token" element={<ShareView />} />
        <Route path="*" element={
          <Layout>
            <Routes>
              <Route path="/" element={<Home />} />
              <Route path="/trips" element={<TripList />} />
              <Route path="/trips/new" element={<TripEditor />} />
              <Route path="/trips/:id" element={<TripDetail />} />
              <Route path="/trips/:id/edit" element={<TripEditor />} />
              <Route path="/timeline" element={<Placeholder name="Timeline" />} />
              <Route path="/stats" element={<Placeholder name="Stats" />} />
            </Routes>
          </Layout>
        } />
      </Routes>
    </BrowserRouter>
  )
}
