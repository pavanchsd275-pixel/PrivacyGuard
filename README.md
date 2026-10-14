# PrivacyGuard

PrivacyGuard is a local-first document privacy app. It combines regular-expression detection with a pretrained PII Transformer (Piiranha), then applies a policy chosen for the document, recipient, and purpose. Users can also protect pasted text, set custom sensitive phrases, and explicitly allow phrases to remain visible.

## Start on Windows

Install Python 3.11 or 3.12, Node.js 18+, and Ollama. From this extracted project, start two terminals:

1. Double-click `run_backend.bat`. It creates a virtual environment and installs Python dependencies on first run. Or run from `backend`:

   ```powershell
   py -3.12 -m venv venv
   .\venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   python -m spacy download en_core_web_sm
   uvicorn app.main:app --reload --port 8000
   ```

2. Double-click `run_frontend.bat`, or run `npm install` and `npm run dev` from `frontend`.
3. Open the Vite URL printed in the frontend terminal (usually http://localhost:5173). The backend health endpoint is http://localhost:8000/health.
4. For document Q&A, run `ollama pull llama3.2:3b` once and ensure Ollama is running.

The first Transformer detection may download about 1.1 GB of model weights. The checkpoint used by `transformer_ner.py` is subject to its upstream CC-BY-NC-ND-4.0 license and is intended here for non-commercial coursework. The optional semantic retrieval model may also download on first question; keyword retrieval is the fallback. This ZIP contains the code and dependency definitions, not Python environments, uploaded documents, or model caches.

## Accounts and privacy

Create an account on the sign-in screen. Passwords are salted and hashed with PBKDF2; session tokens are stored as hashes. Accounts, sessions, protected files, and document metadata are stored locally in `backend/storage`. Original uploads are deleted after processing. Manual phrase values are applied during processing but are not written to metadata; metrics only retain their counts.

This is a local coursework application, not production identity infrastructure. Do not expose its development server to the public internet or use it as the only control for regulated data. Review every protected output before sharing; detection can miss content and document extraction/layout can vary.

## Document workflow

- **Profiles:** Banking & finance, resume & hiring, medical record, legal document, or general.
- **Category controls:** Each profile preselects PII categories, and every category can be changed before processing. Bank statements include account, payment card, PAN, Aadhaar, contact, identity, and password options.
- **Audience and purpose:** Record who will receive the copy and what it is for. The text informs the release decision, while the selected categories and phrases determine the actual redactions.
- **Manual rules:** Add phrases to always protect or phrases to leave visible. They are matched case-insensitively wherever they occur; “always protect” wins if a phrase appears in both lists.
- **Text protection:** Write or paste up to 100,000 characters inside PrivacyGuard and receive the same detection, policy, report, and protected-text view as a file upload.
- **Dashboard:** Per-account totals for documents, detected items, manual rules, risk tiers, and recent documents.
- **Q&A:** Answers use only the protected representation and are checked before display. Q&A requires Ollama.

## Detector and evaluation notes

Regex handles predictable shapes such as email, Indian phone, PAN and Aadhaar patterns. Piiranha adds contextual PII labels such as account numbers, cards, passwords, dates of birth and identity numbers. spaCy NER remains a fallback when the Transformer cannot load. A Transformer confidence score is a model score, not a calibrated probability. Evaluate on representative, consented examples and report precision, recall, and false positives before making strong accuracy claims.

## API overview

- `POST /auth/register`, `POST /auth/login`, `GET /auth/me`, `POST /auth/logout`
- `GET /metrics` — account-scoped dashboard counts and recent activity
- `POST /process` — protect a PDF, DOCX, TXT, or CSV document
- `POST /protect-text` — protect pasted text
- `GET /download/{doc_id}` — download only your protected document
- `POST /chat` — ask about a protected document

Set `VITE_API_BASE` for a non-default API address. Set `NER_BACKEND=auto`, `transformer`, or `spacy` to choose the contextual detector behavior; `auto` tries the Transformer first and falls back to spaCy.
