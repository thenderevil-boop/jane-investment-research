import { useState } from 'react';
import DailyReport from './pages/DailyReport';
import CandidateWorkspace from './pages/CandidateWorkspace';
import EvidenceDashboard from './pages/EvidenceDashboard';
import EvidenceLibrary from './pages/EvidenceLibrary';
import StockResearch from './pages/StockResearch';

type Page = 'daily' | 'stock' | 'candidates' | 'evidence-dashboard' | 'evidence';

export default function App() {
  const [page, setPage] = useState<Page>('stock');
  return (
    <div>
      <nav className="appNav">
        <div className="brand">Jane Research Assistant</div>
        <button className={page === 'stock' ? 'active' : ''} onClick={() => setPage('stock')}>Stock Research</button>
        <button className={page === 'candidates' ? 'active' : ''} onClick={() => setPage('candidates')}>Candidate Workspace</button>
        <button className={page === 'evidence' ? 'active' : ''} onClick={() => setPage('evidence')}>Evidence Library</button>
        <button className={page === 'evidence-dashboard' ? 'active' : ''} onClick={() => setPage('evidence-dashboard')}>Evidence Dashboard</button>
        <button className={page === 'daily' ? 'active' : ''} onClick={() => setPage('daily')}>Daily Report</button>
      </nav>
      <div className="appBoundary">
        <p>Primary workflow: submit a ticker to validate the idea using evidence, data quality, and missing-data checks.</p>
        <p>Candidate Workspace and Evidence tools are supporting local workflow aids, not recommendations or note systems.</p>
      </div>
      {page === 'daily' ? <DailyReport /> : page === 'stock' ? <StockResearch /> : page === 'candidates' ? <CandidateWorkspace /> : page === 'evidence-dashboard' ? <EvidenceDashboard /> : <EvidenceLibrary />}
    </div>
  );
}
