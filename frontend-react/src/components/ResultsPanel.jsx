import { forwardRef } from "react";
import ContractReader from "./ContractReader.jsx";
import BenchmarkResults from "./BenchmarkResults.jsx";
import RedlineResults from "./RedlineResults.jsx";
import Icon from "./Icon.jsx";

const ResultsPanel = forwardRef(function ResultsPanel({
  view, riskData, contractText, sevFilter, onFilterChange,
  benchmarkData, benchmarkLoading, redlineData, redlineLoading,
  onAnalyzeSample,
}, ref) {
  return (
    <main className="main-content" ref={ref}>
      {view === "placeholder" && (
        <div className="card">
          <div className="card-header">
            <Icon name="scale" size={15} />
            <span className="card-title">Get Started</span>
          </div>
          <div className="guide-steps">
            <div className="guide-step">
              <div className="guide-step-num">01</div>
              <div className="guide-step-icon">
                <Icon name="file-text" size={18} />
              </div>
              <div className="guide-step-label">Paste a contract clause or upload a .pdf, .txt, or .md file</div>
            </div>
            <div className="guide-step">
              <div className="guide-step-num">02</div>
              <div className="guide-step-icon">
                <Icon name="search" size={18} />
              </div>
              <div className="guide-step-label">Click Analyze Risk to classify risks across five categories</div>
            </div>
            <div className="guide-step">
              <div className="guide-step-num">03</div>
              <div className="guide-step-icon">
                <Icon name="bar-chart-2" size={18} />
              </div>
              <div className="guide-step-label">Click Benchmark to compare against 116 real SEC EDGAR filings</div>
            </div>
          </div>
          <div className="guide-actions">
            <button className="guide-link" onClick={() => onAnalyzeSample("contract")}>
              <Icon name="file-text" size={13} />
              Try Sample: SaaS Agreement
            </button>
            <button className="guide-link" onClick={() => onAnalyzeSample("privacy")}>
              <Icon name="file-text" size={13} />
              Try Sample: Privacy Policy
            </button>
          </div>
        </div>
      )}

      {view === "risk" && riskData && (
        <ContractReader
          contractText={contractText}
          data={riskData}
          sevFilter={sevFilter}
          onFilterChange={onFilterChange}
        />
      )}

      {view === "benchmark" && (benchmarkData || benchmarkLoading) && (
        <>
          <BenchmarkResults data={benchmarkData} loading={benchmarkLoading} />
          {(redlineData || redlineLoading) && <RedlineResults data={redlineData} loading={redlineLoading} />}
        </>
      )}
    </main>
  );
});

export default ResultsPanel;
