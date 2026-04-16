# Legal Risk Mapper (LRM)

An NLP-powered tool that analyzes contracts, policies, and business text to identify,
classify, and visualize legal risks.

---

## Quick Start

### 1. Install dependencies
```bash
cd legal-risk-mapper
pip install -r requirements.txt
```

### 2. Start the backend
```bash
python -m uvicorn backend.main:app --reload
# API runs at http://localhost:8000
# Swagger docs at http://localhost:8000/docs
```

### 3. Open the frontend
Open `frontend/index.html` in any browser (no build step needed).

### 4. Run the test suite
```bash
python scripts/test_api.py
```

---

## Project Structure

```
legal-risk-mapper/
├── backend/
│   ├── main.py                 # FastAPI app, endpoints
│   ├── models/
│   │   └── schemas.py          # Pydantic request/response models
│   ├── services/
│   │   └── risk_analyzer.py    # Core NLP + rule engine
│   └── utils/
│       └── text_utils.py       # Text cleaning, sentence splitting, TF-IDF
├── frontend/
│   ├── index.html              # Single-page UI
│   ├── style.css               # Styling
│   └── app.js                  # API calls, charts, rendering
├── data/
│   └── sample_inputs/
│       ├── sample_contract.txt
│       └── sample_policy.txt
├── scripts/
│   └── test_api.py             # CLI test runner
├── requirements.txt
└── README.md
```

---

## API Reference

### `GET /health`
Service liveness check.

```json
{ "status": "ok", "version": "1.0.0", "nlp_engine": "rule-based + TF-IDF" }
```

### `POST /analyze`
Analyze raw text.

**Request:**
```json
{
  "text": "Client shall indemnify Company...",
  "document_title": "Service Agreement"
}
```

**Response:**
```json
{
  "document_title": "Service Agreement",
  "total_risks": 5,
  "overall_risk_level": "High",
  "risk_summary": { "Liability Risk": 2, "Financial Risk": 2, "Compliance Risk": 1 },
  "severity_breakdown": { "High": 4, "Medium": 1 },
  "risks": [
    {
      "risk_type": "Liability Risk",
      "severity": "High",
      "text_snippet": "...Client shall indemnify Company...",
      "explanation": "Indemnification clause requires one party to compensate...",
      "score": 0.953,
      "keywords_matched": ["indemnify"]
    }
  ],
  "analysis_notes": "3 HIGH severity issues require immediate legal attention."
}
```

### `POST /analyze/upload`
Upload a `.txt` file (multipart/form-data).

```bash
curl -X POST http://localhost:8000/analyze/upload \
  -F "file=@data/sample_inputs/sample_contract.txt" \
  -F "document_title=My Contract"
```

---

## Risk Categories

| Category | What's Detected |
|---|---|
| **Compliance Risk** | GDPR, HIPAA, CCPA, SOX, PCI-DSS, export controls, sanctions |
| **Liability Risk** | Indemnification, hold harmless, unlimited liability, liquidated damages |
| **Privacy/Data Risk** | PII collection, data selling, third-party sharing, biometrics, tracking |
| **Financial Risk** | Auto-renewal, early termination fees, unilateral price changes, penalties |
| **Contractual Ambiguity** | Sole discretion, "at any time", vague standards, undefined "reasonable" |

---

## Intelligence Architecture

```
Input Text
    │
    ▼
Text Normalization (clean_text)
    │
    ▼
Sentence Segmentation (extract_sentences)
    │
    ▼
Rule-Based Pattern Matching ──── 60+ regex patterns across 5 categories
    │
    ▼
TF-IDF Frequency Boost ──────── Increases confidence for repeated terms
    │
    ▼
Context Window Extraction ────── ±120 chars around each match
    │
    ▼
Near-Duplicate Removal ──────── Jaccard similarity deduplication
    │
    ▼
Severity Escalation ─────────── Cross-category co-occurrence escalation
    │
    ▼
Ranked JSON Output
```

---

## Extending the System

### Add new risk patterns
In `backend/services/risk_analyzer.py`, add entries to `RISK_RULES`:
```python
"Compliance Risk": [
    (r'\byour_new_pattern\b', "High", "Explanation text.", 0.02),
    ...
]
```

### Add spaCy NLP (optional)
```bash
pip install spacy && python -m spacy download en_core_web_sm
```
Then in `risk_analyzer.py`, use `nlp(text).ents` for named entity recognition
to detect jurisdiction names, organization names, etc.

### Add PDF support
```bash
pip install pymupdf
```
```python
import fitz  # PyMuPDF
doc = fitz.open("contract.pdf")
text = "\n".join(page.get_text() for page in doc)
```

---

## Disclaimer

This tool is a prototype for educational and research purposes.
**It is not a substitute for qualified legal advice.**
Always consult a licensed attorney for legal decisions.
