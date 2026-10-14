"""Structured regex and baseline spaCy detectors used by the fusion pipeline."""

import re
from dataclasses import dataclass
from typing import Literal

import spacy

EntitySource = Literal["regex", "ner", "transformer", "propagated", "manual"]


@dataclass
class PIIEntity:
    text: str
    entity_type: str
    start: int
    end: int
    confidence: float
    source: EntitySource


# ---------------------------------------------------------------------------
# 1. REGEX DETECTION
# ---------------------------------------------------------------------------


_REGEX_PATTERNS: dict[str,tuple[str,float]] = {
    "EMAIL": (
        r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
        0.99,
    ),
    "PHONE_IN": (
        
        r"(?<!\d)(?:(?:\+91|0)[\s-]?)?[6-9]\d{9}\b",
        0.90,
    ),
    "PAN_ID": (
        
        r"\b[A-Z]{5}[0-9]{4}[A-Z]\b",
        0.97,
    ),
    "ADDRESS": (
        r"\b\d{1,4}[A-Za-z]?(?:[/-][A-Za-z0-9]+)?,?[ \t]+[A-Z][A-Za-z.]*(?:[ \t]+[A-Z][A-Za-z.]*){0,3}[ \t]+(?:Road|Rd|Street|St|Lane|Nagar|Colony|Avenue|Cross|Main|Layout|Block)\b(?:,?[ \t]+[A-Z][A-Za-z]+(?:[ \t][A-Z][A-Za-z]+)?)?(?:[ \t,-]+\d{6}\b)?",
        0.75,
    ),
    "AADHAAR_ID":(
        r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}\b",
        0.85,
    ),
}

# CVV/CVC values are too short to identify safely by shape alone. Match them
# only when introduced by an explicit card-security label, and redact the
# digits while preserving the surrounding sentence.
_CONTEXT_CAPTURE_PATTERNS: dict[str, tuple[str, float, int]] = {
    "PERSON": (
        r"\b(?:my\s+)?name\s*(?:is\b|:)\s*((?-i:[A-Z][A-Za-z'’-]*(?:[ \t]+[A-Z][A-Za-z'’-]*){0,3}))",
        0.99,
        1,
    ),
    "ACCOUNT_NUM": (
        r"\b(?:bank\s+)?(?:account(?:\s*(?:number|no\.?|#))?|a/c)\b"
        r"[\s,:=#-]*(?:is\b[\s:=#-]*)?(\d(?:[ -]?\d){5,17})\b",
        0.99,
        1,
    ),
    "PASSWORD": (
        r"\b(?:password|passcode|passwd|pwd|pin|secret|credential|"
        r"vault(?:\s+for\s+money)?)\b[\s:=#-]*(?:is\b[\s:=#-]*)?(\S+)",
        0.99,
        1,
    ),
    "CVV": (
        r"\b(?:cvv2?|cvc2?|(?:card\s+)?security\s+code)\b"
        r"[\s:=#-]*(?:is\b[\s:=#-]*)?(\d{3,4})(?!\d)",
        0.99,
        1,
    ),
}

def regex_detect(text: str) -> list[PIIEntity]:
    
    entities = []
    for entity_type,(pattern,confidence) in _REGEX_PATTERNS.items():
        for match in re.finditer(pattern,text):
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

    contextual_entities = []
    for entity_type, (pattern, confidence, value_group) in _CONTEXT_CAPTURE_PATTERNS.items():
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            start, end = match.span(value_group)
            contextual_entities.append(
                PIIEntity(
                    text=text[start:end],
                    entity_type=entity_type,
                    start=start,
                    end=end,
                    confidence=confidence,
                    source="regex",
                )
            )

    # Explicit labels provide stronger evidence than shape-only guesses.
    # For example, a labeled 12-digit account is not necessarily an Aadhaar,
    # and a labeled account/password should replace any overlapping NER span.
    entities = [
        entity for entity in entities
        if not any(entity.start < context.end and entity.end > context.start for context in contextual_entities)
    ]
    entities.extend(contextual_entities)

    return entities


    


# ---------------------------------------------------------------------------
# 2. NER DETECTION
# ---------------------------------------------------------------------------


try:
    nlp = spacy.load("en_core_web_sm")
    NER_AVAILABLE = True
except OSError:
    # Keep the API usable for regex-only detection if the optional spaCy model
    # has not been downloaded yet. /health exposes this state to the UI.
    nlp = None
    NER_AVAILABLE = False




_NER_LABEL_MAP = {
    "PERSON": "PERSON",
    "GPE": "LOCATION",       
    "LOC": "LOCATION",
    "ORG": "ORGANIZATION",
}
_NER_PLACEHOLDER_CONFIDENCE = 0.80

def ner_detect(text: str) -> list[PIIEntity]:
    if nlp is None:
        return []
    doc = nlp(text)
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





    



if __name__ == "__main__":
    test_text = "Rahul Kumar works at Infosys in Chennai. Email: rahul@gmail.com, Phone: 9876543210, PAN: ABCDE1234F"

    print("--- regex_detect ---")
    for e in regex_detect(test_text):
        print(e)

    print("\n--- ner_detect ---")
    for e in ner_detect(test_text):
        print(e)
