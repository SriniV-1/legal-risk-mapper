import Icon from "./Icon.jsx";

export default function InputPanel({
  tab, setTab, inputText, setInputText,
  file, dragging, setDragging, fileInputRef,
  handleFileSet, samples, loadSample,
  error, anyLoading, onAnalyze, onBenchmark, onClear,
}) {
  return (
    <aside className="sidebar">
      {/* TABS */}
      <div className="tabs">
        <button className={`tab-btn${tab === "text" ? " active" : ""}`} onClick={() => setTab("text")}>
          Paste Text
        </button>
        <button className={`tab-btn${tab === "file" ? " active" : ""}`} onClick={() => setTab("file")}>
          Upload File
        </button>
      </div>

      {/* PASTE TEXT */}
      <div className={`tab-panel${tab === "text" ? " active" : ""}`} id="tab-text">
        <textarea
          className="clause-textarea"
          placeholder="Paste a contract clause or section here…"
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
        />
        <div className="char-count">
          {inputText.length.toLocaleString()} character{inputText.length !== 1 ? "s" : ""}
        </div>
      </div>

      {/* UPLOAD FILE */}
      <div className={`tab-panel${tab === "file" ? " active" : ""}`} id="tab-file">
        <div
          className={`dropzone${dragging ? " dragover" : ""}`}
          onClick={() => fileInputRef.current?.click()}
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => { e.preventDefault(); setDragging(false); if (e.dataTransfer.files[0]) handleFileSet(e.dataTransfer.files[0]); }}
        >
          <div className="dropzone-icon">
            <Icon name="upload-cloud" size={24} />
          </div>
          <div className="dropzone-label">Drop file here or click to browse</div>
          <div className="dropzone-hint" style={{ color: "var(--text-3)" }}>.pdf · .txt · .md</div>
        </div>
        {file && (
          <div className="file-selected">
            <Icon name="check-circle" size={13} />
            {file.name} ({(file.size / 1024).toFixed(1)} KB)
          </div>
        )}
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.txt,.md"
          style={{ display: "none" }}
          onChange={(e) => e.target.files[0] && handleFileSet(e.target.files[0])}
        />
      </div>

      {/* SAMPLES */}
      <div className="panel-section">
        <div className="panel-label">Sample Documents</div>
        <div className="samples-list">
          {Object.entries(samples).map(([key, s]) => (
            <button key={key} className="sample-btn" onClick={() => loadSample(key)}>
              <Icon name="file-text" size={13} />
              {s.label}
            </button>
          ))}
        </div>
      </div>

      {/* ERROR */}
      {error && (
        <div className="error-box">
          <Icon name="alert-circle" size={14} />
          <span>{error}</span>
        </div>
      )}

      {/* CONTROLS */}
      <div className="controls-section">
        <div className="btn-row">
          <button className="btn btn-primary" disabled={anyLoading} onClick={onAnalyze}>
            <Icon name="search" size={14} />
            Analyze Risk
          </button>
          <button className="btn btn-secondary" disabled={anyLoading} onClick={onBenchmark}>
            <Icon name="bar-chart-2" size={14} />
            Benchmark
          </button>
        </div>
        <button className="btn btn-ghost btn-full" onClick={onClear}>
          <Icon name="x" size={14} />
          Clear
        </button>
      </div>
    </aside>
  );
}
