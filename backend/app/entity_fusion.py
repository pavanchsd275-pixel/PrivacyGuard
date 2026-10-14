"""
entity_fusion.py — YOUR IMPLEMENTATION (Week 3)

Two responsibilities, deliberately kept as two functions:
    1. fuse_entities(regex_entities, ner_entities) -> list[PIIEntity]
       Merges two entity lists into one, resolving overlaps.
    2. classify_risk(entities) -> dict
       Takes the FUSED list, returns a document-level risk report.

Import PIIEntity from your pii_detector.py (adjust the import if your file
is named differently).
"""

from app.pii_detector import PIIEntity

# ---------------------------------------------------------------------------
# 1. ENTITY FUSION
# ---------------------------------------------------------------------------
#
# TODO: Design and implement fuse_entities().
#
# Steps to think through (don't just start coding — plan first):
#   a) How do you detect if two entities (one from regex, one from NER)
#      overlap in the text? (Hint: compare start/end ranges — see the
#      overlap example in chat above.)
#   b) When two entities DO overlap, which one do you keep? Write down your
#      rule before coding it (e.g. "regex wins because it's deterministic").
#   c) When entities DON'T overlap, what happens to them? (They should both
#      survive into the final list, untouched.)
#   d) What if regex and NER found the EXACT SAME text and type (e.g. both
#      caught "Rahul Kumar" — well, regex wouldn't catch that, but imagine
#      a case where they agree)? Should confidence change when two
#      independent detectors agree on something?
#
# A reasonable approach: start with the regex entities as your base result
# (since regex is highest-precision), then for each NER entity, check if it
# overlaps with anything already in your result. If yes, decide per your
# rule from (b). If no, add it.

def fuse_entities(
    regex_entities: list[PIIEntity],
    ner_entities: list[PIIEntity],
) -> list[PIIEntity]:
    
    fused = list(regex_entities)

    for ner_entity in ner_entities:
        overlapping_regex = [
            regex_entity
            for regex_entity in fused 
            if regex_entity.source == "regex"
            and ner_entity.start < regex_entity.end
            and ner_entity.end > regex_entity.start
        ]

        if overlapping_regex:

            for regex_entity in overlapping_regex:
                if(
                     regex_entity.start == ner_entity.start
                    and regex_entity.end == ner_entity.end
                    and  regex_entity.entity_type == ner_entity.entity_type
                ):
                    regex_entity.confidence = min(
                    1.0,regex_entity.confidence + 0.05
                    )
                    break

            continue  # overlap found: regex wins, so the NER entity is dropped

        fused.append(ner_entity)
    
    
    fused.sort(key=lambda entity: (entity.start, entity.end))
    return fused


            




    




    


# ---------------------------------------------------------------------------
# 2. PRIVACY RISK ENGINE
# ---------------------------------------------------------------------------
#
# TODO: Define a risk tier for each entity_type your detectors can produce.
# Use your original project doc's suggested tiers as a starting point:
#   PERSON, LOCATION      -> MEDIUM
#   EMAIL, PHONE_IN       -> HIGH
#   PAN_ID, AADHAAR_ID     -> CRITICAL
#   ORGANIZATION           -> your call — think about whether an org name
#                              alone is really identifying a PERSON or not

_RISK_TIERS: dict[str, str] = {
    # TODO: fill this in, entity_type -> "LOW" | "MEDIUM" | "HIGH" | "CRITICAL"
    "PERSON": "MEDIUM",
    "LOCATION": "MEDIUM",
    "ORGANIZATION": "LOW",
    "EMAIL": "HIGH",
    "PHONE_IN": "HIGH",
    "ADDRESS": "HIGH",
    "PAN_ID": "CRITICAL",
    "AADHAAR_ID": "CRITICAL",
    
}


def classify_risk(entities: list[PIIEntity]) -> dict:
    """
    TODO:
    1. Count how many entities fall into each risk tier.
    2. Decide a rule for the OVERALL document risk level — your choice, but
       think it through: is it "highest tier present wins", or something
       weighted by count? Either is defensible if you can explain why.
    3. Return a dict shaped roughly like:
       {
           "overall_risk": "HIGH",
           "total_entities": 13,
           "by_tier": {"CRITICAL": 2, "HIGH": 5, "MEDIUM": 6, "LOW": 0},
       }
       (exact shape is your call, but the frontend risk-meter will expect
       SOMETHING like this — keep it reasonably close so wiring it up later
       isn't painful)
    """
    tiers = ("LOW","MEDIUM","HIGH","CRITICAL")
    by_tier = {tier: 0 for tier in tiers}
    for entity in entities :
        tier = _RISK_TIERS.get(entity.entity_type,"LOW")
        by_tier[tier] += 1

    
    overall_risk = "LOW"
    for tier in reversed(tiers):
        if by_tier[tier]>0:
          overall_risk = tier
          break
    return {
        "overall_risk": overall_risk,
        "total_entities": len(entities),
        "by_tier": by_tier,
    }      



       


# ---------------------------------------------------------------------------
# Quick self-test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    from app.pii_detector import regex_detect, ner_detect

    test_text = "Rahul Kumar works at Infosys in Chennai. Email: rahul@gmail.com, Phone: 9876543210, PAN: ABCDE1234F"

    regex_results = regex_detect(test_text)
    ner_results = ner_detect(test_text)

    print(f"Before fusion: {len(regex_results)} regex + {len(ner_results)} ner")

    fused = fuse_entities(regex_results, ner_results)
    print(f"\nAfter fusion: {len(fused)} entities")
    for e in fused:
        print(f"  [{e.entity_type:12}] '{e.text}' (confidence={e.confidence}, source={e.source})")

    risk = classify_risk(fused)
    print(f"\nRisk report: {risk}")
