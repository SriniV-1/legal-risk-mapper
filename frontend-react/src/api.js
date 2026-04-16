// API layer — all backend calls go through here.
// Uses the Vite dev-server proxy: /api/* → http://localhost:8000/*
// In production, change API_BASE to the absolute backend URL.

const API_BASE = "/api";

export async function getHealth() {
  const r = await fetch(`${API_BASE}/health`);
  if (!r.ok) throw new Error(`Health check failed: ${r.status}`);
  return r.json();
}

export async function analyzeText({ text, document_title }) {
  const r = await fetch(`${API_BASE}/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, document_title }),
  });
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: r.statusText }));
    throw new Error(err.detail || "Analysis failed");
  }
  return r.json();
}

export async function analyzeFile(file, document_title) {
  const form = new FormData();
  form.append("file", file);
  if (document_title) form.append("document_title", document_title);
  const r = await fetch(`${API_BASE}/analyze/upload`, { method: "POST", body: form });
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: r.statusText }));
    throw new Error(err.detail || "Upload failed");
  }
  return r.json();
}
