"""
Manual test/demo for document_processor.py.

Run with:  python tests/test_document_processor.py
(run from the backend/ directory so the relative sample_files path resolves)

This is intentionally simple (print-and-eyeball) rather than pytest asserts,
because right now you're verifying EXTRACTION QUALITY (does the text look
right?), not just "did it crash". Once you trust the extractors, convert
this into real pytest assertions.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))  # so `app` package is importable

from app.document_processor import extract_text, UnsupportedFileTypeError

SAMPLE_DIR = Path(__file__).parent / "sample_files"

files_to_test = ["sample.txt", "sample.csv", "sample.docx", "sample.pdf"]

for filename in files_to_test:
    path = SAMPLE_DIR / filename
    print("=" * 60)
    print(f"FILE: {filename}")
    print("=" * 60)
    try:
        result = extract_text(path)
        print(f"Type detected : {result.file_type}")
        print(f"Metadata      : {result.metadata}")
        print(f"Extracted text:\n{result.text}")
    except UnsupportedFileTypeError as e:
        print(f"UNSUPPORTED: {e}")
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")
    print()

# Also test the failure paths on purpose — you want to know these behave
# correctly, not just the happy path.
print("=" * 60)
print("Testing unsupported file type handling")
print("=" * 60)
try:
    extract_text(SAMPLE_DIR / "sample.txt.bak")  # doesn't exist, wrong ext
except UnsupportedFileTypeError as e:
    print(f"Correctly raised UnsupportedFileTypeError: {e}")

print()
print("Testing missing file handling")
try:
    extract_text(SAMPLE_DIR / "does_not_exist.pdf")
except FileNotFoundError as e:
    print(f"Correctly raised FileNotFoundError: {e}")
