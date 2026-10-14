"""
Manual test/demo for pii_detector.py.

Run with:  python tests/test_pii_detector.py

Like test_document_processor.py, this is print-and-eyeball, because right
now you're judging DETECTION QUALITY (did it find the right things? did it
miss anything? did it flag something wrong?), not just "did it crash".
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.document_processor import extract_text
from app.pii_detector import regex_detect, ner_detect

SAMPLE_DIR = Path(__file__).parent / "sample_files"

# A slightly richer test sentence than the sample files — deliberately
# includes a PERSON, LOCATION, ORG, EMAIL, PHONE, and PAN-style ID, so we
# can see how each detector handles a realistic mix.
richer_test_text = """
Rahul Kumar works at Infosys in Chennai.
You can reach him at rahul.kumar@gmail.com or 9876543210.
His PAN number is ABCDE1234F.
Priya Sharma, who lives in Mumbai, is his manager at Infosys.
"""

print("=" * 60)
print("TEST 1: Richer synthetic sentence")
print("=" * 60)
print(f"Input text:\n{richer_test_text}")

regex_results = regex_detect(richer_test_text)
ner_results = ner_detect(richer_test_text)

print(f"\n--- REGEX found {len(regex_results)} entities ---")
for e in regex_results:
    print(f"  [{e.entity_type:12}] '{e.text}'  (confidence: {e.confidence}, pos: {e.start}-{e.end})")

print(f"\n--- NER found {len(ner_results)} entities ---")
for e in ner_results:
    print(f"  [{e.entity_type:12}] '{e.text}'  (confidence: {e.confidence}, pos: {e.start}-{e.end})")

# Now run it on the actual extracted documents from Week 1, to see how it
# performs on realistic (if synthetic) document text.
print("\n" + "=" * 60)
print("TEST 2: Real extracted documents from Week 1")
print("=" * 60)

for filename in ["sample.txt", "sample.docx", "sample.pdf", "sample.csv"]:
    path = SAMPLE_DIR / filename
    doc = extract_text(path)
    regex_results = regex_detect(doc.text)
    ner_results = ner_detect(doc.text)

    print(f"\n{filename}:")
    print(f"  regex: {[(e.entity_type, e.text) for e in regex_results]}")
    print(f"  ner  : {[(e.entity_type, e.text) for e in ner_results]}")
