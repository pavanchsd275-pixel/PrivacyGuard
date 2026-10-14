"""
anonymizer.py — YOUR IMPLEMENTATION (Week 4)

Takes the ORIGINAL text plus the FUSED entity list (from Week 3) and produces
a protected version of the text using three techniques:
    - redact()        -> "[PERSON]"
    - mask()           -> "******3210"
    - pseudonymize()   -> "Person_001" (consistent across repeated mentions)

The main entry point, anonymize_text(), decides WHICH technique to use for
each entity type, then applies it while correctly handling position shifts.
"""

from app.pii_detector import PIIEntity

# ---------------------------------------------------------------------------
# STEP A: Decide which technique applies to which entity type.
# ---------------------------------------------------------------------------
# TODO: fill this in. Suggested starting point (your call, be ready to
# justify it):
#   PERSON                  -> pseudonymize
#   EMAIL, PAN_ID, AADHAAR_ID -> redact
#   PHONE_IN                 -> mask
#   LOCATION                 -> redact (or pseudonymize — your call, think
#                                about whether repeated location mentions
#                                matter for later Q&A the way repeated
#                                person mentions do)
#   ORGANIZATION              -> your call — recall risk tier was LOW, does
#                                 that change whether you anonymize it at all?

_STRATEGY: dict[str, str] = {
   "PERSON": "pseudonymize",
    "EMAIL": "redact",
    "PAN_ID": "redact",
    "AADHAAR_ID": "redact",
    "PHONE_IN": "mask",
    "LOCATION": "redact",
    "ORGANIZATION": "redact",
    "ADDRESS": "redact",
    "CVV": "redact",
}

_PRESERVE_GROUPS = {"CONTACT": {"EMAIL", "PHONE_IN"}}


# ---------------------------------------------------------------------------
# STEP B: The three technique functions. Each takes ONE entity and returns
# the replacement string for it. They do NOT touch the full text — that
# happens in anonymize_text() below.
# ---------------------------------------------------------------------------

def redact(entity: PIIEntity) -> str:
    return f"[{entity.entity_type}]"
    


def mask(entity: PIIEntity) -> str:
    value = entity.text
    if len(value) <= 4:
        return "*" * len(value)

    return "*" * (len(value) - 4) + value[-4:]


# TODO: You'll need some persistent storage for pseudonym mappings AND a
# counter per entity type, since "Rahul Kumar" must map to the SAME
# "Person_001" every time it appears. A dict is fine, but think about: where
# should this dict live so it persists across multiple calls within ONE
# document, but doesn't leak into the NEXT document processed?
# (Hint: a class, or a dict passed in and mutated, both work — pick one and
# be ready to explain why you avoided a plain module-level global dict.)

def pseudonymize(entity: PIIEntity, mapping: dict, counters: dict) -> str:

    key = (entity.text.strip().lower(), entity.entity_type)

    if key in mapping:
        return mapping[key]

    entity_type = entity.entity_type
    counters[entity_type] = counters.get(entity_type, 0) + 1

    pseudonym = f"{entity_type.title()}_{counters[entity_type]:03d}"


    mapping[key] = pseudonym

    return pseudonym
# ---------------------------------------------------------------------------
# STEP C: The main function — apply everything to the full text.
# ---------------------------------------------------------------------------

def anonymize_text(text: str, entities: list[PIIEntity], mapping: dict | None = None, counters: dict | None = None, preserve_types: set[str] | None = None) -> str:
    entities = sorted(
        entities,
        key=lambda e: e.start,
        reverse=True
    )
    mapping = {} if mapping is None else mapping
    counters = {} if counters is None else counters
    preserve_types = preserve_types or set()

    for entity in entities:

        strategy = _STRATEGY.get(
            entity.entity_type,
            "redact"
        )

        if entity.entity_type in preserve_types or any(
            entity.entity_type in _PRESERVE_GROUPS.get(group, set()) for group in preserve_types
        ):
            strategy = "keep"

        if strategy == "keep":
            continue

        if strategy == "redact":
            replacement = redact(entity)

        elif strategy == "mask":
            replacement = mask(entity)

        elif strategy == "pseudonymize":
            replacement = pseudonymize(
                entity,
                mapping,
                counters
            )

        else:
            replacement = redact(entity)

        text = (
            text[:entity.start]
            + replacement
            + text[entity.end:]
        )

    return text


# ---------------------------------------------------------------------------
# Quick self-test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    from app.pii_detector import regex_detect, ner_detect
    from app.entity_fusion import fuse_entities

    test_text = (
        "Rahul Kumar works at Infosys in Chennai. "
        "Email: rahul@gmail.com, Phone: 9876543210, PAN: ABCDE1234F. "
        "Rahul Kumar's manager is Priya Sharma."
    )

    regex_results = regex_detect(test_text)
    ner_results = ner_detect(test_text)
    fused = fuse_entities(regex_results, ner_results)

    protected = anonymize_text(test_text, fused)

    print("ORIGINAL:")
    print(test_text)
    print("\nPROTECTED:")
    print(protected)
    print("\nCheck: does 'Rahul Kumar' map to the SAME pseudonym both times it appears?")
