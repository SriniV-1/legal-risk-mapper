/**
 * UploadPanel — the main input card.
 * Three tabs: Paste text, Upload file, Load sample.
 * Shows prominent Analyze button with loading state.
 */
import { useState, useRef } from "react";
import { SAMPLES } from "../samples.js";

export default function UploadPanel({ onAnalyze, isAnalyzing, error }) {
  const [tab, setTab] = useState("text");
  const [text, setText] = useState("");
  const [title, setTitle] = useState("");
  const [file, setFile] = useState(null);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef(null);

  // ── Action: clicking "Analyze" ──
  const handleAnalyze = () => {
    if (tab === "file" && file) {
      onAnalyze({ mode: "file", file, title });
    } else if (text.trim().length >= 10) {
      onAnalyze({ mode: "text", text: text.trim(), title: title.trim() || null });
    }
  };

  // ── Action: clicking a sample card ──
  const loadSample = (key) => {
    const s = SAMPLES[key];
    setText(s.text);
    setTitle(s.docTitle);
    setTab("text");
  };

  const handleClear = () => {
    setText("");
    setTitle("");
    setFile(null);
  };

  const handleFile = (f) => {
    if (f && (f.name.endsWith(".txt") || f.name.endsWith(".md"))) setFile(f);
  };

  const canAnalyze =
    (tab === "file" && file) ||
    (tab !== "file" && text.trim().length >= 10);

  return (
    <div className="card p-6 lg:p-7 animate-fade-in">
      {/* ── Header ── */}
      <div className="flex items-start justify-between mb-5">
        <div>
          <h2 className="text-[17px] font-bold text-slate-900 tracking-tight">Document Input</h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Paste text, upload a file, or load a sample to begin
          </p>
        </div>
      </div>

      {/* ── Tabs ── */}
      <div className="flex gap-1 p-1 bg-slate-100 rounded-xl border border-slate-200 mb-5">
        {[
          { id: "text",   label: "Paste Text", icon: "✎" },
          { id: "file",   label: "Upload File", icon: "↑" },
          { id: "sample", label: "Samples",     icon: "✦" },
        ].map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-sm font-semibold transition-all ${
              tab === t.id
                ? "bg-white text-blue-600 shadow-sm"
                : "text-slate-500 hover:text-slate-900"
            }`}
          >
            <span>{t.icon}</span> {t.label}
          </button>
        ))}
      </div>

      {/* ── Tab: Paste text ── */}
      {tab === "text" && (
        <div className="space-y-4 animate-fade-in">
          <div>
            <label className="field-label">
              Document title <span className="text-slate-400 font-normal normal-case">(optional)</span>
            </label>
            <input
              type="text"
              placeholder="e.g. SaaS Service Agreement"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="field-input"
            />
          </div>
          <div>
            <label className="field-label">Contract / Policy Text</label>
            <textarea
              rows={12}
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="Paste your contract, terms of service, privacy policy, or business description here…"
              className="field-input font-mono text-[13px] leading-relaxed resize-y min-h-[260px] scrollbar-thin"
            />
            <div className="text-right text-xs text-slate-400 mt-1.5 tabular-nums">
              {text.length.toLocaleString()} characters
            </div>
          </div>
        </div>
      )}

      {/* ── Tab: Upload file ── */}
      {tab === "file" && (
        <div className="animate-fade-in">
          <label className="field-label">Document title <span className="text-slate-400 font-normal normal-case">(optional)</span></label>
          <input
            type="text"
            placeholder="e.g. My Contract"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="field-input mb-4"
          />

          <div
            onClick={() => fileInputRef.current?.click()}
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragOver(false);
              handleFile(e.dataTransfer.files[0]);
            }}
            className={`rounded-2xl border-2 border-dashed p-10 text-center cursor-pointer transition-all ${
              dragOver
                ? "border-blue-600 bg-blue-50 scale-[1.01]"
                : "border-slate-300 bg-slate-50 hover:border-blue-400 hover:bg-blue-50/50"
            }`}
          >
            <div className="text-5xl mb-3">📄</div>
            <p className="text-slate-700 font-semibold mb-1">
              Drag & drop a <code className="bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded font-semibold">.txt</code> file
            </p>
            <p className="text-xs text-slate-500 mb-4">or click to browse</p>
            <input
              ref={fileInputRef}
              type="file"
              accept=".txt,.md"
              hidden
              onChange={(e) => handleFile(e.target.files[0])}
            />
            {file && (
              <p className="text-sm font-semibold text-blue-600 mt-3">
                ✓ {file.name} ({(file.size / 1024).toFixed(1)} KB)
              </p>
            )}
          </div>
        </div>
      )}

      {/* ── Tab: Samples ── */}
      {tab === "sample" && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 animate-fade-in">
          {Object.values(SAMPLES).map((s) => (
            <button
              key={s.id}
              onClick={() => loadSample(s.id)}
              className="text-left p-4 rounded-xl border-[1.5px] border-slate-200 bg-slate-50 hover:border-blue-500 hover:bg-white hover:-translate-y-0.5 hover:shadow-md transition-all"
            >
              <div className="text-2xl mb-2">{s.icon}</div>
              <div className="text-sm font-bold text-slate-900 mb-1">{s.title}</div>
              <div className="text-xs text-slate-500 leading-relaxed">{s.description}</div>
            </button>
          ))}
        </div>
      )}

      {/* ── Error ── */}
      {error && (
        <div className="mt-5 p-3.5 rounded-lg border border-red-200 bg-red-50 text-red-700 text-sm whitespace-pre-wrap animate-fade-in">
          ⚠ {error}
        </div>
      )}

      {/* ── Action bar ── */}
      <div className="flex items-center gap-3 mt-6 pt-5 border-t border-slate-200">
        <button
          onClick={handleAnalyze}
          disabled={!canAnalyze || isAnalyzing}
          className="btn-primary"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="11" cy="11" r="7" /><line x1="21" y1="21" x2="16" y2="16" />
          </svg>
          {isAnalyzing ? "Analyzing…" : "Analyze Risk"}
        </button>
        <button onClick={handleClear} className="btn-ghost">Clear</button>
      </div>
    </div>
  );
}
