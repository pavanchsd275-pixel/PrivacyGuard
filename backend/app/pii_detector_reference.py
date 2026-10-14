"""
pii_detector.py

Step 3 of the PrivacyGuard architecture: PII Detection.

Two independent detectors, deliberately NOT merged yet:
    1. regex_detect()  — deterministic pattern matching (email, phone, PAN-style ID)
    2. ner_detect()    — contextual detection via a pretrained NER model (spaCy)

Why keep them separate instead of one big function?
Your architecture diagram shows Regex and NER as parallel branches that only
combine at "Entity Fusion" (Week 3). If we merged them now, we couldn't
independently test/tune each detector's accuracy — and fusion logic (what do
we do when regex and NER disagree, or overlap?) is its own real design
problem we shouldn't hide inside detection.

Every entity found, from either detector, is represented the same way
(PIIEntity) so Week 3's fusion step has a consistent shape to work with —
same normalization principle as ExtractedDocument in document_processor.py.
"""

import re
from dataclasses import dataclass
from typing import Literal

import spacy

EntitySource = Literal["regex", "ner"]


@dataclass
class PIIEntity:
    text: str            # the actual matched string, e.g. "rahul@gmail.com"
    entity_type: str      # e.g. "EMAIL", "PHONE", "PERSON", "LOCATION"
    start: int            # character offset in the source text (inclusive)
    end: int               # character offset in the source text (exclusive)
    confidence: float     # 0.0-1.0
    source: EntitySource  # which detector found it — needed for fusion later


# ---------------------------------------------------------------------------
# 1. Regex detection — deterministic, high precision, no context understanding
# ---------------------------------------------------------------------------
#
# Confidence for regex matches is fixed and high, because a regex either
# matches the exact pattern or it doesn't — there's no "maybe" the way a
# neural model has. We still assign values <1.0 for patterns that are more
# prone to false positives (e.g. a 10-digit PHONE could coincidentally be
# some other number).

_REGEX_PATTERNS: dict[str, tuple[str, float]] = {
    "EMAIL": (
        r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
        0.99,
    ),
    "PHONE_IN": (
        # Indian 10-digit mobile numbers, optionally prefixed with +91 or 0
        r"(?:(?:\+91|0)[\s-]?)?[6-9]\d{9}\b",
        0.90,
    ),
    "PAN_ID": (
        # Indian PAN card format: 5 letters, 4 digits, 1 letter (e.g. ABCDE1234F)
        r"\b[A-Z]{5}[0-9]{4}[A-Z]\b",
        0.97,
    ),
    "AADHAAR_ID": (
        # Indian Aadhaar: 12 digits, often space/hyphen grouped as 4-4-4
        r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}\b",
        0.85,  # lower confidence — a generic 12-digit number could be many things
    ),
}


def regex_detect(text: str) -> list[PIIEntity]:
    entities = []
    for entity_type, (pattern, confidence) in _REGEX_PATTERNS.items():
        for match in re.finditer(pattern, text):
            entities.append(
                PIIEntity(
                    text=match.group(),
                    entity_type=entity_type,
                    start=match.start(),
                    end=match.end(),
                    confidence=confidence,
                    source="regex",
                )
            )
    return entities


# ---------------------------------------------------------------------------
# 2. NER detection — contextual, understands "this word is a name because of
#    how it's used in the sentence", not just its shape.
# ---------------------------------------------------------------------------

# We only load the spaCy model ONCE (not per-request) — loading it is slow
# (~1 second), so doing it at import time means the API stays fast after startup.
_nlp = spacy.load("en_core_web_sm")

# spaCy's built-in labels we care about for privacy, mapped to our naming scheme.
# spaCy also detects things like DATE, MONEY, CARDINAL — we ignore those here
# because they're not inherently identifying on their own.
_NER_LABEL_MAP = {
    "PERSON": "PERSON",
    "GPE": "LOCATION",       # GPE = Geo-Political Entity (city/state/country)
    "LOC": "LOCATION",
    "ORG": "ORGANIZATION",
}

# spaCy's small model doesn't output a real confidence score per entity
# (that requires the "transformer" pipeline, which is heavier). We use a
# fixed placeholder confidence for now and revisit this honestly in the
# evaluation section of your report — it's a known limitation of the small
# model, not something to hide.
_NER_PLACEHOLDER_CONFIDENCE = 0.80


def ner_detect(text: str) -> list[PIIEntity]:
    doc = _nlp(text)
    entities = []
    for ent in doc.ents:
        if ent.label_ not in _NER_LABEL_MAP:
            continue
        entities.append(
            PIIEntity(
                text=ent.text,
                entity_type=_NER_LABEL_MAP[ent.label_],
                start=ent.start_char,
                end=ent.end_char,
                confidence=_NER_PLACEHOLDER_CONFIDENCE,
                source="ner",
            )
        )
    return entities


# ---------------------------------------------------------------------------
# Combined (but NOT fused) — just runs both and returns both lists separately.
# Real fusion (deduping overlaps, resolving conflicts) is Week 3.
# ---------------------------------------------------------------------------

def detect_all(text: str) -> dict[str, list[PIIEntity]]:
    return {
        "regex": regex_detect(text),
        "ner": ner_detect(text),
    }
