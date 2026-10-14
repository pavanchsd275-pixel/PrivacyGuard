"""PrivacyGuard API: local accounts, policy-based protection, metrics, and Q&A."""

import json
import re
import shutil
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, HTTPException, Form, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.document_processor import extract_text, UnsupportedFileTypeError
from app.pii_detector import regex_detect, ner_detect, PIIEntity
from app.pii_detector import NER_AVAILABLE
from app.document_writer import analyze, backend_status, write_protected
from app.entity_fusion import _RISK_TIERS
from app.llm import ask_llm, LLMUnavailable
from app.privacy_verifier import verify_answer
from app import rag
from app.auth import current_user, login as login_user, register as register_user, revoke
from app.policy_profiles import DEFAULT_PROTECT_TYPES, ENTITY_TYPES, PROFILE_DEFAULTS
from app.anonymizer import anonymize_text

app = FastAPI(title="PrivacyGuard API")

# Allow the Vite dev server (default port 5173) to call this API during development.
# NOTE: tighten this before any real deployment — wide open CORS is fine for
# local dev only.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class AuthRequest(BaseModel):
    email: str
    password: str
    name: str = ""


@app.post("/auth/register")
def auth_register(payload: AuthRequest):
    return register_user(payload.name, payload.email, payload.password)


@app.post("/auth/login")
def auth_login(payload: AuthRequest):
    return login_user(payload.email, payload.password)


@app.get("/auth/me")
def auth_me(user: dict = Depends(current_user)):
    return user


@app.post("/auth/logout")
def auth_logout(authorization: str | None = Header(default=None)):
    from fastapi.security import HTTPAuthorizationCredentials

    token = authorization.split(" ", 1)[1] if authorization and authorization.lower().startswith("bearer ") else None
    revoke(HTTPAuthorizationCredentials(scheme="Bearer", credentials=token) if token else None)
    return {"ok": True}


@app.get("/health")
def health():
    """Quick sanity check endpoint — hit this first to confirm the server is up."""
    return {"status": "ok", "ner_model": "available" if NER_AVAILABLE else "missing (regex detection remains available)", "detector": backend_status()}


def _split_values(value: str | None) -> list[str]:
    return list(dict.fromkeys(item.strip() for item in re.split(r"[\n;,]+", value or "") if item.strip()))


def _protection_policy(protect_types: str | None, preserve_types: str, profile: str, manual_protect: list[str]) -> tuple[set[str], set[str]]:
    if profile not in PROFILE_DEFAULTS:
        raise HTTPException(400, "Choose a supported document profile.")
    if protect_types is not None:
        protect = {item.upper() for item in _split_values(protect_types)}
    else:
        # Backwards compatibility for earlier builds that sent preserve-types.
        preserve_legacy = {item.strip().upper() for item in preserve_types.split(",") if item.strip()}
        protect = set(ENTITY_TYPES) - preserve_legacy if preserve_legacy else set(PROFILE_DEFAULTS.get(profile, DEFAULT_PROTECT_TYPES))
    if not protect.issubset(ENTITY_TYPES):
        raise HTTPException(400, "Unknown PII category in protection policy.")
    if manual_protect:
        protect.add("CUSTOM_PII")
    preserve = set(ENTITY_TYPES) - protect
    return protect, preserve


def _document_result(doc_dir: Path, filename: str, suffix: str, extracted_text: str, entities: list[PIIEntity], risk: dict, protected_text: str, profile: str, audience: str, purpose: str, protect: set[str], manual_protect: list[str], manual_allow: list[str], user_id: str) -> dict:
    doc_id = doc_dir.name
    residual = [
        entity for entity in regex_detect(protected_text)
        if entity.entity_type in protect and not any(term.casefold() in entity.text.casefold() for term in manual_allow)
    ]
    (doc_dir / "protected_text.txt").write_text(protected_text, encoding="utf-8")
    meta = {
        "filename": filename, "suffix": suffix, "audience": audience[:100], "purpose": purpose[:300],
        "profile": profile, "protect_types": sorted(protect), "preserve_types": sorted(ENTITY_TYPES - protect),
        # Keep counts for metrics, never persist the actual manual phrases.
        "manual_protect_count": len(manual_protect), "manual_allow_count": len(manual_allow), "user_id": user_id,
        "created_at": datetime.now(timezone.utc).isoformat(), "entity_count": len(entities),
        "protected_items": sum(e.entity_type in protect or e.source == "manual" for e in entities), "risk": risk,
    }
    (doc_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    return {
        "doc_id": doc_id, "filename": filename, "file_type": suffix.lstrip("."),
        "original_text": extracted_text, "protected_text": protected_text,
        "entities": [{**_entity_to_dict(e), "tier": _RISK_TIERS.get(e.entity_type, "LOW")} for e in entities],
        "risk": risk, "protected_items": sum(e.entity_type in protect or e.source == "manual" for e in entities),
        "residual_structured_pii": len(residual), "ner_backend": backend_status()["active"],
        "audience": audience, "purpose": purpose, "profile": profile, "protect_types": sorted(protect),
        "preserve_types": sorted(ENTITY_TYPES - protect), "manual_protect_count": len(manual_protect),
        "download_url": f"/download/{doc_id}",
    }


@app.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    """
    Accepts a PDF/DOCX/TXT/CSV file, extracts its text, returns it.

    We write the upload to a temp file because our extractors (PyMuPDF,
    python-docx, pandas) all expect a file PATH, not an in-memory stream.
    This is a normal pattern for file-processing APIs.
    """
    suffix = Path(file.filename).suffix.lower()

    if suffix not in {".pdf", ".docx", ".txt", ".csv"}:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{suffix}'. Use PDF, DOCX, TXT, or CSV.",
        )

    # Write to a temp file with the same suffix so our extractors' suffix
    # detection still works correctly.
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        contents = await file.read()
        tmp.write(contents)
        tmp_path = tmp.name

    try:
        result = extract_text(tmp_path)
    except UnsupportedFileTypeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Catch-all so a malformed file (corrupt PDF etc.) returns a clean
        # error instead of a raw 500 stack trace to the frontend.
        raise HTTPException(status_code=422, detail=f"Could not process file: {e}")
    finally:
        Path(tmp_path).unlink(missing_ok=True)  # always clean up the temp file

    return {
        "doc_id": str(uuid.uuid4()),  # placeholder id — real persistence comes in Week 4
        "filename": file.filename,
        "file_type": result.file_type,
        "text": result.text,
        "metadata": result.metadata,
    }


class DetectPIIRequest(BaseModel):
    text: str


def _entity_to_dict(e: PIIEntity) -> dict:
    return {
        "text": e.text,
        "entity_type": e.entity_type,
        "start": e.start,
        "end": e.end,
        "confidence": e.confidence,
        "source": e.source,
    }


@app.post("/detect-pii")
async def detect_pii(payload: DetectPIIRequest):
    """
    Step 3 of the architecture: PII Detection.

    Takes raw text (from the /upload response) and runs BOTH detectors on it.
    Returns them as SEPARATE lists on purpose — we are not fusing them yet
    (that's Week 3's Entity Fusion step). The frontend shows both so you can
    see, side by side, where regex and NER agree or disagree.
    """
    if not payload.text.strip():
        raise HTTPException(status_code=400, detail="No text provided to scan.")

    regex_entities = regex_detect(payload.text)
    ner_entities = ner_detect(payload.text)

    return {
        "regex_entities": [_entity_to_dict(e) for e in regex_entities],
        "ner_entities": [_entity_to_dict(e) for e in ner_entities],
        "regex_count": len(regex_entities),
        "ner_count": len(ner_entities),
    }


# ---------------------------------------------------------------------------
# Functionality 1, end to end: /process + /download
# ---------------------------------------------------------------------------
# Storage is deliberately simple (plain folders, no database/encryption - that
# was scoped out). One privacy-minded rule though: the ORIGINAL file is deleted
# as soon as the protected copy exists, so only the protected version stays on
# disk - and later the RAG/LLM stage only ever reads that protected version.

STORAGE_DIR = Path(__file__).resolve().parent.parent / "storage"
STORAGE_DIR.mkdir(exist_ok=True)


@app.post("/process")
async def process_document(
    file: UploadFile = File(...),
    audience: str = Form("faculty"),
    purpose: str = Form("Review this document"),
    preserve_types: str = Form("ORGANIZATION,LOCATION"),
    protect_types: str | None = Form(None),
    profile: str = Form("general"),
    manual_protect: str = Form(""),
    manual_allow: str = Form(""),
    user: dict = Depends(current_user),
):
    """Upload -> detect -> fuse -> risk score -> anonymize -> protected file."""
    suffix = Path(file.filename).suffix.lower()
    if suffix not in {".pdf", ".docx", ".txt", ".csv"}:
        raise HTTPException(400, f"Unsupported file type '{suffix}'. Use PDF, DOCX, TXT, or CSV.")

    doc_id = str(uuid.uuid4())
    manual_protect_terms = _split_values(manual_protect)
    manual_allow_terms = _split_values(manual_allow)
    protect, preserve = _protection_policy(protect_types, preserve_types, profile, manual_protect_terms)
    doc_dir = STORAGE_DIR / doc_id
    doc_dir.mkdir()
    original = doc_dir / f"original{suffix}"
    protected = doc_dir / f"protected{suffix}"
    original.write_bytes(await file.read())

    try:
        extracted = extract_text(original)
        entities, risk = analyze(extracted.text, manual_protect=manual_protect_terms, manual_allow=manual_allow_terms)
        write_protected(original, protected, preserve, manual_protect_terms, manual_allow_terms)
        protected_text = extract_text(protected).text
    except Exception as e:
        shutil.rmtree(doc_dir, ignore_errors=True)
        raise HTTPException(422, f"Could not process file: {e}")
    finally:
        original.unlink(missing_ok=True)  # never keep the raw document

    return _document_result(
        doc_dir, file.filename, suffix, extracted.text, entities, risk, protected_text,
        profile, audience, purpose, protect, manual_protect_terms, manual_allow_terms, user["id"],
    )


class TextProtectionRequest(BaseModel):
    text: str = Field(min_length=1, max_length=100_000)
    audience: str = "Personal review"
    purpose: str = "Protect pasted text"
    profile: str = "general"
    protect_types: list[str] | None = None
    manual_protect: list[str] = Field(default_factory=list)
    manual_allow: list[str] = Field(default_factory=list)


@app.post("/protect-text")
def protect_text_endpoint(payload: TextProtectionRequest, user: dict = Depends(current_user)):
    manual_protect = _split_values("\n".join(payload.manual_protect))
    manual_allow = _split_values("\n".join(payload.manual_allow))
    policy_string = ",".join(payload.protect_types) if payload.protect_types is not None else None
    protect, preserve = _protection_policy(policy_string, "", payload.profile, manual_protect)
    entities, risk = analyze(payload.text, manual_protect=manual_protect, manual_allow=manual_allow)
    protected = anonymize_text(payload.text, entities, preserve_types=preserve)
    doc_id = str(uuid.uuid4())
    doc_dir = STORAGE_DIR / doc_id
    doc_dir.mkdir()
    (doc_dir / "protected.txt").write_text(protected, encoding="utf-8")
    return _document_result(
        doc_dir, "Protected text.txt", ".txt", payload.text, entities, risk, protected,
        payload.profile, payload.audience, payload.purpose, protect, manual_protect, manual_allow, user["id"],
    )


@app.get("/metrics")
def get_metrics(user: dict = Depends(current_user)):
    totals = {"documents": 0, "entities": 0, "protected_items": 0, "manual_rules": 0}
    risks = {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0}
    recent = []
    if STORAGE_DIR.exists():
        for folder in STORAGE_DIR.iterdir():
            meta_path = folder / "meta.json"
            if not meta_path.is_file():
                continue
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if meta.get("user_id") != user["id"]:
                continue
            totals["documents"] += 1
            totals["entities"] += int(meta.get("entity_count", 0))
            totals["protected_items"] += int(meta.get("protected_items", 0))
            totals["manual_rules"] += int(meta.get("manual_protect_count", 0))
            report = meta.get("risk", {})
            for tier, count in report.get("by_tier", {}).items():
                if tier in risks:
                    risks[tier] += int(count)
            recent.append({
                "doc_id": folder.name, "filename": meta.get("filename", "Document"),
                "profile": meta.get("profile", "general"), "audience": meta.get("audience", ""),
                "overall_risk": report.get("overall_risk", "LOW"),
                "entity_count": int(meta.get("entity_count", 0)), "created_at": meta.get("created_at", ""),
            })
    recent.sort(key=lambda item: item["created_at"], reverse=True)
    return {"totals": totals, "risk_breakdown": risks, "recent_documents": recent[:6]}


@app.get("/download/{doc_id}")
def download_protected(doc_id: str, user: dict = Depends(current_user)):
    try:
        uuid.UUID(doc_id)  # rejects anything that isn't a UUID (blocks path tricks)
    except ValueError:
        raise HTTPException(400, "Invalid document id.")
    doc_dir = STORAGE_DIR / doc_id
    meta_path = doc_dir / "meta.json"
    if not meta_path.exists():
        raise HTTPException(404, "Document not found.")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if meta.get("user_id") != user["id"]:
        raise HTTPException(404, "Document not found.")
    protected = doc_dir / f"protected{meta['suffix']}"
    return FileResponse(protected, filename=f"{Path(meta['filename']).stem}_protected{meta['suffix']}")


# ---------------------------------------------------------------------------
# Functionality 2: privacy-aware chat over the PROTECTED document
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You answer questions about a document in which personal information has been "
    "replaced by placeholders such as [EMAIL], [PHONE_IN], [PERSON], [LOCATION] or "
    "pseudonyms like Person_001. Rules: use ONLY the provided context. Never guess, "
    "invent or complete names, contact details, addresses or ID numbers. If asked for "
    "information that appears as a placeholder or is not in the context, say it is "
    "protected or not available. Refer to people by the pseudonyms exactly as written. "
    "Keep answers short."
)


class ChatRequest(BaseModel):
    doc_id: str
    question: str


def _chat_impl(payload: ChatRequest, user: dict):
    """Question -> retrieve protected chunks -> LLM -> privacy verification -> safe answer."""
    try:
        uuid.UUID(payload.doc_id)
    except ValueError:
        raise HTTPException(400, "Invalid document id.")
    question = payload.question.strip()
    if not question:
        raise HTTPException(400, "Ask a question first.")

    text_path = STORAGE_DIR / payload.doc_id / "protected_text.txt"
    if not text_path.exists():
        raise HTTPException(404, "Document not found. Upload it again.")
    meta_path = text_path.parent / "meta.json"
    if not meta_path.exists() or json.loads(meta_path.read_text(encoding="utf-8")).get("user_id") != user["id"]:
        raise HTTPException(404, "Document not found.")

    protected_text = text_path.read_text(encoding="utf-8")
    try:
        if not rag.is_indexed(payload.doc_id):
            rag.index_document(payload.doc_id, protected_text)
        chunks = rag.retrieve(payload.doc_id, question)
    except ImportError:
        chunks = rag.keyword_retrieve(protected_text, question)
    except Exception:
        # First-run model downloads or incompatible embedding installs should
        # not make document Q&A unavailable; retrieval fallback still uses
        # protected text only.
        chunks = rag.keyword_retrieve(protected_text, question)

    context = "\n---\n".join(chunks)
    user_prompt = f"Context:\n{context}\n\nQuestion: {question}"
    try:
        raw_answer = ask_llm(_SYSTEM_PROMPT, user_prompt)
    except LLMUnavailable as e:
        raise HTTPException(503, str(e))

    verdict = verify_answer(raw_answer)  # the raw answer is never sent to the browser
    return {
        "answer": verdict["safe_answer"],
        "status": verdict["status"],
        "findings": verdict["findings"],
        "sources": chunks,
    }


@app.post("/chat")
def chat(payload: ChatRequest, user: dict = Depends(current_user)):
    """Wraps the chat logic so ANY failure comes back as readable JSON (an unhandled
    crash would show up in the browser as a vague 'could not reach the server')."""
    try:
        return _chat_impl(payload, user)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"{type(e).__name__}: {e}")
