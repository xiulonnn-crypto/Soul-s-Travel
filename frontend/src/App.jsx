import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'

function Placeholder({ name }) {
  return <div style={{ padding: 40, fontSize: 20, color: '#8e99a4' }}>{name} - Coming Soon</div>
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/share/:token" element={<Placeholder name="Share" />} />
        <Route path="*" element={
          <Layout>
            <Routes>
              <Route path="/" element={<Placeholder name="Home" />} />
              <Route path="/trips" element={<Placeholder name="Trips" />} />
              <Route path="/trips/new" element={<Placeholder name="New Trip" />} />
              <Route path="/trips/:id" element={<Placeholder name="Trip Detail" />} />
              <Route path="/trips/:id/edit" element={<Placeholder name="Edit Trip" />} />
              <Route path="/timeline" element={<Placeholder name="Timeline" />} />
              <Route path="/stats" element={<Placeholder name="Stats" />} />
            </Routes>
          </Layout>
        } />
      </Routes>
    </BrowserRouter>
  )
}
