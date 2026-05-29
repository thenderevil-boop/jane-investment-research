import { useState } from 'react';
import DailyReport from './pages/DailyReport';
import CandidateWorkspace from './pages/CandidateWorkspace';
import EvidenceDashboard from './pages/EvidenceDashboard';
import EvidenceLibrary from './pages/EvidenceLibrary';
import OperationsDiagnostics from './pages/OperationsDiagnostics';
import StockResearch from './pages/StockResearch';

type Page = 'daily' | 'stock' | 'candidates' | 'evidence-dashboard' | 'evidence' | 'operations';

function initialPageFromLocation(): Page {
  if (typeof window === 'undefined') return 'stock';
  if (window.location.pathname.startsWith('/daily-report')) return 'daily';
  if (window.location.pathname.startsWith('/operations')) return 'operations';
  if (window.location.pathname.startsWith('/stock-research')) return 'stock';
  return 'stock';
}

export default function App() {
  const [page, setPage] = useState<Page>(() => initialPageFromLocation());
  return (
    <div>
      <nav className="appNav">
        <div className="brand">Jane Research Assistant</div>
        <button className={page === 'stock' ? 'active' : ''} onClick={() => setPage('stock')}>Stock Research</button>
        <button className={page === 'candidates' ? 'active' : ''} onClick={() => setPage('candidates')}>Candidate Workspace</button>
        <button className={page === 'evidence' ? 'active' : ''} onClick={() => setPage('evidence')}>Evidence Library</button>
        <button className={page === 'evidence-dashboard' ? 'active' : ''} onClick={() => setPage('evidence-dashboard')}>Evidence Dashboard</button>
        <button className={page === 'daily' ? 'active' : ''} onClick={() => setPage('daily')}>Daily Report</button>
        <button className={page === 'operations' ? 'active' : ''} onClick={() => setPage('operations')}>Operations Diagnostics</button>
      </nav>
      <div className="appBoundary">
        <p>Primary workflow: submit a ticker to validate the idea using evidence, data quality, and missing-data checks.</p>
        <p>Candidate Workspace and Evidence tools are supporting local workflow aids, not recommendations or note systems.</p>
      </div>
      {page === 'daily' ? <DailyReport /> : page === 'operations' ? <OperationsDiagnostics /> : page === 'stock' ? <StockResearch /> : page === 'candidates' ? <CandidateWorkspace /> : page === 'evidence-dashboard' ? <EvidenceDashboard /> : <EvidenceLibrary />}
    </div>
  );
}
