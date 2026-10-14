"""
transformer_ner.py

The "Transformer-based NER" block from your architecture.

WHY THIS EXISTS
Regex only finds things with a fixed SHAPE (email, PAN, phone). spaCy's small
model only knows general news-style entities (person, place, organization), so
it cannot know that "werre@#123" is a password or that "123456789012" is a bank
account. Instead of writing a new regex for every kind of sensitive data, we use
a transformer that was ALREADY fine-tuned for PII detection on a large labelled
dataset (ai4privacy). We do NOT train anything: we only run it (inference).

MODEL
iiiorg/piiranha-v1-detect-personal-information  (mDeBERTa-v3-base, ~1.1 GB)
It tags tokens as one of 17 PII types: given name, surname, email, telephone,
street, building number, city, zip code, password, username, account number,
credit card, date of birth, driver licence, id card, social number, tax number.
Licence: cc-by-nc-nd-4.0 (non-commercial - fine for coursework, cite it).

WHAT THIS FILE DOES
1. splits long text into small chunks (the model reads ~256-512 tokens at once)
2. runs the model, maps its labels to OUR entity types
3. merges neighbouring pieces: GIVENNAME + SURNAME -> one PERSON,
   BUILDINGNUM + STREET + CITY -> one ADDRESS
4. returns PIIEntity objects, exactly like regex_detect / ner_detect, so the
   rest of the pipeline (fusion, risk, anonymization) does not change.

First run downloads the model (~1.1 GB, once). Try it:
    python -m app.transformer_ner
"""

import os
import re

from app.pii_detector import PIIEntity

MODEL_NAME = os.environ.get("PII_MODEL", "iiiorg/piiranha-v1-detect-personal-information")
MIN_SCORE = float(os.environ.get("PII_MIN_SCORE", "0.55"))
CHUNK_CHARS = 400

# model label  ->  our entity type
LABEL_MAP = {
    "GIVENNAME": "PERSON",
    "SURNAME": "PERSON",
    "EMAIL": "EMAIL",
    "TELEPHONENUM": "PHONE_IN",
    "PASSWORD": "PASSWORD",
    "USERNAME": "USERNAME",
    "ACCOUNTNUM": "ACCOUNT_NUM",
    "CREDITCARDNUMBER": "CREDIT_CARD",
    "DATEOFBIRTH": "DATE_OF_BIRTH",
    "DRIVERLICENSENUM": "ID_NUMBER",
    "IDCARDNUM": "ID_NUMBER",
    "SOCIALNUM": "ID_NUMBER",
    "TAXNUM": "ID_NUMBER",
    "STREET": "ADDRESS",
    "BUILDINGNUM": "ADDRESS",
    "ZIPCODE": "ADDRESS",
    "CITY": "LOCATION",
}

_pipe = None  # loaded on first use; tests replace it with a fake


def _get_pipe():
    global _pipe
    if _pipe is None:
        from transformers import pipeline  # imported late so the app starts without it

        _pipe = pipeline("token-classification", model=MODEL_NAME, aggregation_strategy="simple")
    return _pipe


def _chunks(text: str, size: int = CHUNK_CHARS):
    """Yield (offset, piece). Pieces are contiguous slices of `text`, cut at a
    newline or space when possible, so offsets stay exact and nothing is lost."""
    pos, n = 0, len(text)
    while pos < n:
        end = min(pos + size, n)
        if end < n:
            cut = text.rfind("\n", pos, end)
            if cut <= pos + size // 3:
                cut = text.rfind(" ", pos, end)
            if cut > pos + size // 3:
                end = cut + 1
        piece = text[pos:end]
        if piece.strip():
            yield pos, piece
        pos = end


_GAP = re.compile(r"^[ \t,.\-/]{0,3}$")  # only a space, comma, dot... between two pieces


def _merged_type(a: str, b: str) -> str | None:
    if a == b and a in ("PERSON", "ADDRESS"):
        return a
    if {a, b} == {"ADDRESS", "LOCATION"}:  # street + city = one address
        return "ADDRESS"
    return None


def _merge(entities: list[PIIEntity], text: str) -> list[PIIEntity]:
    out: list[PIIEntity] = []
    for e in sorted(entities, key=lambda e: e.start):
        if out:
            prev = out[-1]
            merged = _merged_type(prev.entity_type, e.entity_type)
            if merged and e.start >= prev.end and _GAP.match(text[prev.end:e.start]):
                prev.entity_type = merged
                prev.end = e.end
                prev.text = text[prev.start:prev.end]
                prev.confidence = round((prev.confidence + e.confidence) / 2, 4)
                continue
        out.append(e)
    return out


def transformer_detect(text: str) -> list[PIIEntity]:
    if not text.strip():
        return []
    pieces = list(_chunks(text))
    results = _get_pipe()([piece for _, piece in pieces], batch_size=8)

    found: list[PIIEntity] = []
    for (offset, _), items in zip(pieces, results):
        for item in items:
            label = item["entity_group"].upper()
            if label[:2] in ("B-", "I-"):
                label = label[2:]
            entity_type = LABEL_MAP.get(label)
            if entity_type is None or item["score"] < MIN_SCORE:
                continue
            start, end = offset + item["start"], offset + item["end"]
            found.append(
                PIIEntity(
                    text=text[start:end],
                    entity_type=entity_type,
                    start=start,
                    end=end,
                    confidence=round(float(item["score"]), 4),
                    source="transformer",
                )
            )
    return _merge(found, text)


if __name__ == "__main__":
    sample = (
        "My name is Yashwant Kumar and my phone number is 9876543210. "
        "I live at 12 ABC Street, Chennai, and my account number is 123456789012.\n"
        "i am software engineer by profession\n"
        "my vtop password is werre@#123"
    )
    print("Loading model (first run downloads ~1.1 GB)...")
    for e in transformer_detect(sample):
        print(f"  {e.entity_type:14} {e.text!r:28} confidence={e.confidence}")
