"""
document_writer.py

Step 8 of the architecture: turn the anonymization logic into a real
protected FILE in the same format the user uploaded.

Two ideas to understand here:

1. analyze(text) combines regex detection with the configured contextual
   detector (Transformer first, spaCy fallback), fuses candidates, applies
   manual protect/allow phrases, and computes a risk summary.

2. Each format is protected in the way that best preserves its structure:
       TXT  - protect the whole text at once (best NER context)
       DOCX - protect paragraph by paragraph, in place (keeps styles, tables)
       CSV  - protect cell by cell, keeping the column header as context
       PDF  - true redaction in place: the original text is REMOVED from the
              file (not just covered with a box) and the replacement is
              written in its spot
   A single `mapping`/`counters` pair is shared across the whole document, so
   "Rahul Kumar" becomes the SAME Person_00X in every paragraph/cell/page.
"""

import os
import re
from pathlib import Path

import docx
import pandas as pd
import pymupdf

from app.anonymizer import _PRESERVE_GROUPS, _STRATEGY, anonymize_text, mask, pseudonymize, redact
from app.entity_fusion import _RISK_TIERS, classify_risk, fuse_entities
from app.pii_detector import PIIEntity, ner_detect, regex_detect


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

# Entity types that only the transformer detector can produce. Registering them
# here gives them a risk tier (shown in the Risk Report) and a protection strategy.
_RISK_TIERS.update({
    "PASSWORD": "CRITICAL", "ACCOUNT_NUM": "CRITICAL", "CREDIT_CARD": "CRITICAL", "CVV": "CRITICAL",
    "ID_NUMBER": "CRITICAL", "USERNAME": "HIGH", "DATE_OF_BIRTH": "HIGH",
    "CUSTOM_PII": "HIGH",
})
_STRATEGY.update({
    t: "redact" for t in ("PASSWORD", "ACCOUNT_NUM", "CREDIT_CARD", "CVV", "ID_NUMBER", "USERNAME", "DATE_OF_BIRTH")
})
_STRATEGY["CUSTOM_PII"] = "redact"

# The small spaCy model is noisy on resumes/forms. These two sets remove the
# most common false alarms WITHOUT touching real PII:
#   * field labels and tech/skill words it mistakes for organizations/places
#   * job titles it mistakes for people ("Machine Learning Intern")
# Every rule here trades a little precision for readable documents - say so
# in your report (it's a documented limitation, not a hidden hack).
_NOT_PII = {
    "phone", "pan", "email", "e-mail", "address", "name", "contact", "skills",
    "experience", "education", "summary", "projects", "dob", "aadhaar", "aadhar",
    "mobile", "linkedin", "github", "resume", "cv",
    "python", "java", "javascript", "typescript", "sql", "mysql", "postgresql",
    "mongodb", "docker", "kubernetes", "react", "angular", "vue", "node", "fastapi",
    "flask", "django", "tensorflow", "pytorch", "keras", "scikit-learn", "sklearn",
    "pandas", "numpy", "spacy", "nlp", "ml", "ai", "llm", "bert", "git", "aws",
    "azure", "gcp", "linux", "html", "css", "c", "c++", "c#", "r", "excel",
    "tableau", "power bi", "opencv", "hugging face", "huggingface",
    "machine learning", "deep learning", "data science", "b.tech", "m.tech",
    "b.e", "bsc", "msc", "mba",
    # Common resume vocabulary frequently hallucinated as PERSON/ORG by the
    # small general-purpose English model.
    "algorithms", "algorithm", "rag", "ner", "lms", "pii", "c/c++",
    "data structures", "coding practice", "machine", "privacy-preserving ai",
    "ai & ml", "ai/ml", "computer science", "computer science and engineering",
    "vellore institute of technology", "vit", "faculty", "leetcode",
    "privacyguard", "privacy guard", "deep learning", "generative ai",
    "pii detection, anonymization and secure rag",
}
_ROLE_WORDS = {
    "intern", "engineer", "developer", "manager", "analyst", "scientist", "student",
    "consultant", "lead", "associate", "trainee", "architect", "director",
    "officer", "executive", "designer",
}


def _clean_ner(entities: list[PIIEntity], min_person_tokens: int = 2) -> list[PIIEntity]:
    cleaned = []
    for e in entities:
        stripped = e.text.strip().split("\n")[0].strip()  # an entity never spans lines
        if not stripped:
            continue
        e.start += len(e.text) - len(e.text.lstrip())  # NER sometimes swallows a trailing newline
        e.end = e.start + len(stripped)
        e.text = stripped
        key = stripped.lower().strip(" .,:;")
        if key in _NOT_PII:
            continue
        # Avoid protecting generic single-token model guesses. A single
        # capitalized skill or heading is not sufficient evidence of a person.
        if e.entity_type == "PERSON" and len(key.split()) < min_person_tokens:
            continue
        if e.entity_type == "PERSON" and any(w in _ROLE_WORDS for w in key.split()):
            continue
        cleaned.append(e)
    return cleaned


def propagate(text: str, entities: list[PIIEntity], known: dict | None = None) -> list[PIIEntity]:
    """NER often catches a name in one sentence and misses it in the next.
    Once a value has been recognised ANYWHERE, flag every other exact
    occurrence of it too (skipping spots already covered by another entity)."""
    taken = [(e.start, e.end) for e in entities]
    values = {(e.text, e.entity_type): e.confidence for e in entities if e.source in ("ner", "transformer")}
    values.update(known or {})  # values recognised elsewhere in the document
    extra = []
    for (value, entity_type), confidence in values.items():
        for m in re.finditer(rf"(?<!\w){re.escape(value)}(?!\w)", text):
            if any(m.start() < end and m.end() > start for start, end in taken):
                continue
            taken.append((m.start(), m.end()))
            extra.append(PIIEntity(value, entity_type, m.start(), m.end(),
                                   round(confidence * 0.95, 2), "propagated"))
    return sorted(entities + extra, key=lambda e: (e.start, e.end))


# Which contextual detector runs: "auto" (transformer, falling back to spaCy if it
# cannot be loaded), "transformer" (fail loudly), or "spacy" (the baseline).
_requested_backend = os.environ.get("NER_BACKEND", "auto").lower()
_transformer_error: str | None = None
_backend_status = {"requested": _requested_backend, "active": "not used yet", "error": None}


def set_ner_backend(name: str) -> None:
    """Used by evaluate.py to compare detectors."""
    global _requested_backend, _transformer_error
    _requested_backend = name.lower()
    _transformer_error = None
    _backend_status.update(requested=_requested_backend, active="not used yet", error=None)


def backend_status() -> dict:
    return dict(_backend_status)


def _detect_ner(text: str) -> list[PIIEntity]:
    """Contextual detection: names, addresses, passwords, account numbers...
    Transformer first; spaCy only as a fallback or when asked for explicitly."""
    global _transformer_error
    if _requested_backend != "spacy":
        if _transformer_error is None:
            try:
                from app.transformer_ner import transformer_detect

                entities = transformer_detect(text)
                _backend_status["active"] = "transformer"
                return _clean_ner(entities, min_person_tokens=1)
            except Exception as e:  # not installed, no internet, out of memory...
                _transformer_error = f"{type(e).__name__}: {e}"
                _backend_status["error"] = _transformer_error
                if _requested_backend == "transformer":
                    raise
                print(f"[PrivacyGuard] transformer unavailable, falling back to spaCy: {_transformer_error}")
        elif _requested_backend == "transformer":
            raise RuntimeError(_transformer_error)
    _backend_status["active"] = "spacy"
    return _clean_ner(ner_detect(text))


def _find_manual_spans(text: str, terms: list[str] | None) -> list[tuple[int, int, str]]:
    spans = []
    for term in dict.fromkeys((item.strip() for item in (terms or []) if item.strip())):
        spans.extend((m.start(), m.end(), term) for m in re.finditer(re.escape(term), text, flags=re.IGNORECASE))
    return spans


def analyze(
    text: str,
    known: dict | None = None,
    manual_protect: list[str] | None = None,
    manual_allow: list[str] | None = None,
) -> tuple[list[PIIEntity], dict]:
    """Detect -> clean -> fuse -> propagate -> score. Returns (entities, risk_report).
    `known` = values already recognised elsewhere in the same document."""
    regex_entities = regex_detect(text)
    ner_entities = _detect_ner(text)
    # A shape-only regex ("12 digits = Aadhaar?") should not outvote a model that
    # read the sentence and saw "my account number is ...".
    contextual = [e for e in ner_entities if e.entity_type in ("ACCOUNT_NUM", "CREDIT_CARD") and e.confidence >= 0.8]
    regex_entities = [
        r for r in regex_entities
        if not (r.entity_type == "AADHAAR_ID" and any(r.start < c.end and r.end > c.start for c in contextual))
    ]
    fused = fuse_entities(regex_entities, ner_entities)
    fused = propagate(text, fused, known)
    protected_spans = _find_manual_spans(text, manual_protect)
    allowed_spans = _find_manual_spans(text, manual_allow)
    # Explicit protect instructions win conflicts with the allow-list.
    fused = [e for e in fused if not any(e.start < end and e.end > start for start, end, _ in protected_spans)]
    fused = [
        e for e in fused
        if e.source == "manual" or not any(e.start < end and e.end > start for start, end, _ in allowed_spans)
    ]
    fused.extend(
        PIIEntity(text[start:end], "CUSTOM_PII", start, end, 1.0, "manual")
        for start, end, _ in protected_spans
    )
    fused.sort(key=lambda e: (e.start, e.end))
    return fused, classify_risk(fused)


def collect_known(full_text: str) -> dict:
    """Whole-document pre-pass: which names/places/orgs were recognised anywhere?"""
    fused, _ = analyze(full_text)
    return {(e.text, e.entity_type): e.confidence for e in fused if e.source in ("ner", "transformer", "propagated")}


def protect_text(
    text: str,
    mapping: dict,
    counters: dict,
    known: dict | None = None,
    preserve_types: set[str] | None = None,
    manual_protect: list[str] | None = None,
    manual_allow: list[str] | None = None,
) -> str:
    """Anonymize a piece of text, sharing pseudonym state with the caller."""
    if not text.strip():
        return text
    fused, _ = analyze(text, known, manual_protect, manual_allow)
    return anonymize_text(text, fused, mapping, counters, preserve_types)


def replacement_for(entity: PIIEntity, mapping: dict, counters: dict, preserve_types: set[str] | None = None) -> str | None:
    """Same strategy table as anonymize_text, but for ONE entity (PDF needs this).
    Returns None when the strategy is 'keep'."""
    strategy = _STRATEGY.get(entity.entity_type, "redact")
    if preserve_types and (entity.entity_type in preserve_types or any(
        entity.entity_type in _PRESERVE_GROUPS.get(group, set()) for group in preserve_types
    )):
        strategy = "keep"
    if strategy == "keep":
        return None
    if strategy == "mask":
        return mask(entity)
    if strategy == "pseudonymize":
        return pseudonymize(entity, mapping, counters)
    return redact(entity)


# ---------------------------------------------------------------------------
# Per-format writers
# ---------------------------------------------------------------------------

def _write_txt(src: Path, dst: Path, mapping: dict, counters: dict, preserve_types: set[str], manual_protect: list[str], manual_allow: list[str]) -> None:
    text = src.read_text(encoding="utf-8", errors="replace")
    dst.write_text(protect_text(text, mapping, counters, preserve_types=preserve_types, manual_protect=manual_protect, manual_allow=manual_allow), encoding="utf-8")


def _protect_paragraph(paragraph, mapping: dict, counters: dict, known: dict, preserve_types: set[str], manual_protect: list[str], manual_allow: list[str]) -> None:
    original = paragraph.text
    if not original.strip():
        return
    protected = protect_text(original, mapping, counters, known, preserve_types, manual_protect, manual_allow)
    if protected == original:
        return
    # A paragraph is split into "runs" (pieces with their own formatting).
    # We put the protected text in the first run and empty the rest, so the
    # paragraph keeps its style but no original text survives.
    if paragraph.runs:
        paragraph.runs[0].text = protected
        for run in paragraph.runs[1:]:
            run.text = ""
    else:
        paragraph.add_run(protected)


def _write_docx(src: Path, dst: Path, mapping: dict, counters: dict, preserve_types: set[str], manual_protect: list[str], manual_allow: list[str]) -> None:
    document = docx.Document(src)

    all_text = [p.text for p in document.paragraphs]
    for table in document.tables:
        for row in table.rows:
            all_text += [cell.text for cell in row.cells]
    known = collect_known("\n".join(all_text))  # names found anywhere count everywhere

    for paragraph in document.paragraphs:
        _protect_paragraph(paragraph, mapping, counters, known, preserve_types, manual_protect, manual_allow)

    seen_cells = set()  # merged cells appear several times; protect each once,
    for table in document.tables:  # otherwise "Person_001" gets re-processed
        for row in table.rows:
            for cell in row.cells:
                if id(cell._tc) in seen_cells:
                    continue
                seen_cells.add(id(cell._tc))
                for paragraph in cell.paragraphs:
                    _protect_paragraph(paragraph, mapping, counters, known, preserve_types, manual_protect, manual_allow)

    document.save(dst)


def _write_csv(src: Path, dst: Path, mapping: dict, counters: dict, preserve_types: set[str], manual_protect: list[str], manual_allow: list[str]) -> None:
    df = pd.read_csv(src, dtype=str, keep_default_na=False)
    known = collect_known("\n".join(f"{c}: {v}" for c in df.columns for v in df[c] if v.strip()))
    for column in df.columns:
        prefix = f"{column}: "  # gives NER the same context the extractor gives it
        for idx, value in df[column].items():
            if not value.strip():
                continue
            candidate = prefix + value
            fused, _ = analyze(candidate, known, manual_protect, manual_allow)
            # ignore anything detected inside the header label itself
            fused = [e for e in fused if e.start >= len(prefix)]
            protected = anonymize_text(candidate, fused, mapping, counters, preserve_types)
            df.at[idx, column] = protected[len(prefix):]
    df.to_csv(dst, index=False)


def _write_pdf(src: Path, dst: Path, mapping: dict, counters: dict, preserve_types: set[str], manual_protect: list[str], manual_allow: list[str]) -> None:
    doc = pymupdf.open(src)
    known = collect_known("\n".join(page.get_text() for page in doc))
    for page in doc:
        fused, _ = analyze(page.get_text(), known, manual_protect, manual_allow)
        handled = set()
        for entity in sorted(fused, key=lambda e: e.start):  # forward = natural numbering
            if entity.text in handled:
                continue
            handled.add(entity.text)
            replacement = replacement_for(entity, mapping, counters, preserve_types)
            if replacement is None:
                continue
            for rect in page.search_for(entity.text):
                # shrink the font so the replacement fits inside the original
                # box; never enlarge the box, or we'd wipe out neighbouring text
                width_at_1pt = pymupdf.get_text_length(replacement, fontname="helv", fontsize=1)
                size = min(11, rect.height * 0.8, rect.width / width_at_1pt)
                page.add_redact_annot(
                    rect, text=replacement, fontname="helv",
                    fontsize=max(size, 4), fill=(1, 1, 1),
                )
        page.apply_redactions()  # this is what actually deletes the original text
    doc.save(dst, garbage=4, deflate=True)


_WRITERS = {
    ".txt": _write_txt,
    ".docx": _write_docx,
    ".csv": _write_csv,
    ".pdf": _write_pdf,
}


def write_protected(
    src: str | Path,
    dst: str | Path,
    preserve_types: set[str] | None = None,
    manual_protect: list[str] | None = None,
    manual_allow: list[str] | None = None,
) -> None:
    """Create a protected copy of `src` at `dst`, in the same file format."""
    src, dst = Path(src), Path(dst)
    writer = _WRITERS.get(src.suffix.lower())
    if writer is None:
        raise ValueError(f"Unsupported file type: {src.suffix}")
    writer(src, dst, {}, {}, preserve_types or set(), manual_protect or [], manual_allow or [])  # fresh mapping/counters per document
