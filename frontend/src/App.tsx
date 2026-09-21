import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import AnalysisLanding from './pages/AnalysisLanding'
import AnalysisBuilder from './pages/AnalysisBuilder'
import AnalysisRun from './pages/AnalysisRun'
import AnalysisResults from './pages/AnalysisResults'
import ReportsCenter from './pages/ReportsCenter'
import ReportViewer from './pages/ReportViewer'
import Variants from './pages/Variants'
import VariantDetail from './pages/VariantDetail'
import Protein from './pages/Protein'
import Structure from './pages/Structure'
import AnalysisCharts from './pages/AnalysisCharts'
import Literature from './pages/Literature'
import Methodology from './pages/Methodology'
import Settings from './pages/Settings'
import { ThemeProvider } from './theme'

export default function App() {
  return (
    <ThemeProvider>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/analysis" element={<AnalysisLanding />} />
          <Route path="/analysis/new" element={<AnalysisBuilder />} />
          <Route path="/analysis/:sid/run" element={<AnalysisRun />} />
          <Route path="/analysis/:sid/results" element={<AnalysisResults />} />
          <Route path="/reports" element={<ReportsCenter />} />
          <Route path="/reports/:rid" element={<ReportViewer />} />
          <Route path="/variants" element={<Variants />} />
          <Route path="/variants/:uid" element={<VariantDetail />} />
          <Route path="/protein" element={<Protein />} />
          <Route path="/structure" element={<Structure />} />
          <Route path="/analysis-charts" element={<AnalysisCharts />} />
          <Route path="/literature" element={<Literature />} />
          <Route path="/methodology" element={<Methodology />} />
          <Route path="/settings" element={<Settings />} />
        </Route>
      </Routes>
    </ThemeProvider>
  )
}
