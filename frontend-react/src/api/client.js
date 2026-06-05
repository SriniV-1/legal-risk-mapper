const API_BASE =
  import.meta.env.VITE_API_BASE_URL ||
  "http://localhost:8000";

async function handleResponse(res) {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      if (body.detail) detail = body.detail;
    } catch {
      // ignore parse errors
    }
    throw new Error(detail);
  }
  return res.json();
}

export async function checkHealth() {
  const res = await fetch(`${API_BASE}/health`);
  return handleResponse(res);
}

export async function analyzeText(text) {
  const res = await fetch(`${API_BASE}/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  return handleResponse(res);
}

export async function analyzeFile(file) {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}/analyze/upload`, {
    method: "POST",
    body: form,
  });
  return handleResponse(res);
}

export async function extractText(file) {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}/extract`, {
    method: "POST",
    body: form,
  });
  return handleResponse(res);
}

export async function benchmarkText(text, clauseType = "auto") {
  const res = await fetch(`${API_BASE}/benchmark`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, clause_type: clauseType }),
  });
  return handleResponse(res);
}

export async function generateRedlines(text, clauseType) {
  const res = await fetch(`${API_BASE}/redline`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, clause_type: clauseType }),
  });
  return handleResponse(res);
}

export async function compareContracts(contracts, clauseType) {
  const res = await fetch(`${API_BASE}/compare`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ contracts, clause_type: clauseType }),
  });
  return handleResponse(res);
}
