import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { UploadPage } from './pages/UploadPage';
import { ResultsPage } from './pages/ResultsPage';
import { ReportPage } from './pages/ReportPage';

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<UploadPage />} />
        <Route path="/results/:jobId" element={<ResultsPage />} />
        <Route path="/report/:jobId" element={<ReportPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Router>
  );
}

export default App;
