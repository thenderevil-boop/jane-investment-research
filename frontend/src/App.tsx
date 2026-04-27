import { useState } from 'react';
import DailyReport from './pages/DailyReport';
import StockResearch from './pages/StockResearch';

type Page = 'daily' | 'stock';

export default function App() {
  const [page, setPage] = useState<Page>('daily');
  return (
    <div>
      <nav className="appNav">
        <div className="brand">Jane Research Assistant</div>
        <button className={page === 'daily' ? 'active' : ''} onClick={() => setPage('daily')}>Daily Report</button>
        <button className={page === 'stock' ? 'active' : ''} onClick={() => setPage('stock')}>Stock Research</button>
      </nav>
      {page === 'daily' ? <DailyReport /> : <StockResearch />}
    </div>
  );
}
