"""
privacy_verifier.py

Step 12 of the architecture: Privacy Verification of the LLM's answer.

The LLM only ever sees the PROTECTED document, so in theory it cannot leak
real PII. In practice it can still (a) hallucinate plausible-looking contact
details when asked for them, or (b) repeat something the detector missed
earlier. So every answer is re-scanned with the SAME detection engine before
the user sees it:

    HIGH / CRITICAL item found (email, phone, PAN, Aadhaar, address)
        -> BLOCKED   the whole answer is withheld
    MEDIUM item found (a real-looking name or place)
        -> REDACTED  that item is replaced by [TYPE], the rest is shown
    nothing found
        -> PASSED

Our own placeholders ("[EMAIL]", "Person_001", "******3210") are not PII and
are ignored, otherwise every correct answer would fail its own check.
"""

import re

from app.anonymizer import redact
from app.document_writer import analyze
from app.entity_fusion import _RISK_TIERS

_PLACEHOLDER = re.compile(r"\[[A-Z_]+\]|\b[A-Za-z]+_\d{3}\b|\*{3,}\d{0,4}")
_BLOCK_TIERS = {"HIGH", "CRITICAL"}

BLOCKED_MESSAGE = (
    "I can't share that. The answer would have contained personal information "
    "(for example contact details or ID numbers), which this system protects."
)


def verify_answer(answer: str) -> dict:
    entities, _ = analyze(answer)
    placeholder_spans = [(m.start(), m.end()) for m in _PLACEHOLDER.finditer(answer)]

    findings = [
        e for e in entities
        if not any(e.start < end and e.end > start for start, end in placeholder_spans)
    ]

    blocking = [e for e in findings if _RISK_TIERS.get(e.entity_type) in _BLOCK_TIERS]
    summary = [{"entity_type": e.entity_type, "tier": _RISK_TIERS.get(e.entity_type, "LOW")} for e in findings]

    if blocking:
        return {"status": "BLOCKED", "safe_answer": BLOCKED_MESSAGE, "findings": summary}

    if findings:
        safe = answer
        for e in sorted(findings, key=lambda e: e.start, reverse=True):  # back to front, same trick as anonymizer
            safe = safe[:e.start] + redact(e) + safe[e.end:]
        return {"status": "REDACTED", "safe_answer": safe, "findings": summary}

    return {"status": "PASSED", "safe_answer": answer, "findings": []}
