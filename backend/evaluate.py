"""
evaluate.py - Step 14: evaluation with real numbers, comparing the two detectors.

Run from the backend folder (venv active):
    python evaluate.py                      # compares spaCy baseline vs transformer
    python evaluate.py --backend spacy      # one detector only
    python evaluate.py --semantic           # also original-vs-protected similarity

It builds synthetic documents whose PII is known BY CONSTRUCTION (no real
people's data), runs the full pipeline with each detector, and reports:
  * Precision / Recall / F1 per entity type ("strict": value AND type must match)
  * Lenient recall: was the value detected as ANY entity? (what privacy cares about)
  * Leakage rate: % of PII values still readable in the protected text
Results are written to evaluation_report.md for your report.
"""

import argparse
import random
import statistics

from app.document_writer import analyze, protect_text, set_ner_backend, backend_status

FIRST = ["Rahul", "Priya", "Arjun", "Ananya", "Karthik", "Divya", "Vikram", "Sneha", "Rohan", "Meera", "Aditya", "Kavya"]
LAST = ["Kumar", "Sharma", "Iyer", "Reddy", "Patel", "Nair", "Singh", "Menon", "Gupta", "Das", "Rao", "Verma"]
CITIES = ["Chennai", "Mumbai", "Bengaluru", "Hyderabad", "Pune", "Delhi", "Kolkata", "Coimbatore", "Madurai", "Jaipur"]
ORGS = ["Infosys", "Wipro", "Zoho", "Flipkart", "Accenture", "Cognizant", "Deloitte"]
STREETS = ["Gandhi", "Nehru", "Anna", "Park", "Temple", "Lake", "Station"]
SKILLS = ["Python", "SQL", "TensorFlow", "Docker", "React", "FastAPI", "PyTorch", "Git"]
PW_WORDS = ["werre", "blue", "tiger", "mango", "delta", "orbit"]
TYPES = ["PERSON", "EMAIL", "PHONE_IN", "PAN_ID", "AADHAAR_ID", "ADDRESS", "LOCATION",
         "USERNAME", "PASSWORD", "ACCOUNT_NUM"]


def make_doc(rng: random.Random):
    first, last = rng.choice(FIRST), rng.choice(LAST)
    name = f"{first} {last}"
    city, org = rng.choice(CITIES), rng.choice(ORGS)
    email = f"{first.lower()}.{last.lower()}{rng.randint(1, 99)}@gmail.com"
    phone = str(rng.choice("6789")) + "".join(str(rng.randint(0, 9)) for _ in range(9))
    letters = "ABCDEFGHJKLMNPQRSTUVWXYZ"
    pan = "".join(rng.choice(letters) for _ in range(5)) + f"{rng.randint(1000, 9999)}" + rng.choice(letters)
    aadhaar = " ".join(f"{rng.randint(1000, 9999)}" for _ in range(3))
    address = f"{rng.randint(1, 99)} {rng.choice(STREETS)} Road, {city}"
    username = f"{first.lower()}{rng.randint(10, 99)}"
    password = rng.choice(PW_WORDS) + rng.choice("@#$!%") + str(rng.randint(100, 999))
    account = str(rng.randint(10_000_000_000, 99_999_999_999))  # 11 digits, no fixed "shape"
    skills = ", ".join(rng.sample(SKILLS, 4))
    text = (
        f"{name}\n"
        f"Email: {email} | Phone: {phone}\n"
        f"PAN: {pan} | Aadhaar: {aadhaar}\n"
        f"Address: {address}\n"
        f"My account number is {account}.\n"
        f"My portal username is {username} and my password is {password}.\n"
        f"Skills: {skills}\n"
        f"{name} worked at {org} in {city} as a software engineer and built an NLP project.\n"
        f"{name} presented the work to the leadership team.\n"
    )
    gold = [(name, "PERSON"), (email, "EMAIL"), (phone, "PHONE_IN"), (pan, "PAN_ID"),
            (aadhaar, "AADHAAR_ID"), (address, "ADDRESS"), (city, "LOCATION"),
            (username, "USERNAME"), (password, "PASSWORD"), (account, "ACCOUNT_NUM")]
    return text, gold


def prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return p, r, f


def run(backend: str, docs, semantic: bool):
    set_ner_backend(backend)
    tp = {t: 0 for t in TYPES}; fp = {t: 0 for t in TYPES}; fn = {t: 0 for t in TYPES}
    leak = {t: [0, 0] for t in TYPES}  # [leaked, total]
    total = detected = leaked = 0
    sims = []
    for text, gold in docs:
        entities, _ = analyze(text)
        pred = {(e.text, e.entity_type) for e in entities}
        gold_set = set(gold)
        for value, typ in gold:
            total += 1
            tp[typ] += (value, typ) in pred
            fn[typ] += (value, typ) not in pred
            detected += any(value in e.text or e.text in value for e in entities)
        for e in entities:
            if (e.text, e.entity_type) not in gold_set and e.entity_type in fp:
                fp[e.entity_type] += 1
        protected = protect_text(text, {}, {})
        for value, typ in gold:
            leak[typ][1] += 1
            if value in protected:
                leaked += 1; leak[typ][0] += 1
        if semantic:
            from app import rag
            a, b = rag.embedder.embed([text, protected])
            sims.append(sum(x * y for x, y in zip(a, b)))
    return dict(tp=tp, fp=fp, fn=fn, leak=leak, total=total, detected=detected, leaked=leaked,
                sims=sims, active=backend_status()["active"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs", type=int, default=40)
    ap.add_argument("--backend", choices=["spacy", "transformer", "both"], default="both")
    ap.add_argument("--semantic", action="store_true")
    args = ap.parse_args()

    rng = random.Random(42)
    docs = [make_doc(rng) for _ in range(args.docs)]
    names = ["spacy", "transformer"] if args.backend == "both" else [args.backend]
    results = {}
    for name in names:
        try:
            print(f"Running detector: {name} ...")
            results[name] = run(name, docs, args.semantic)
        except Exception as e:
            print(f"  could not run '{name}': {type(e).__name__}: {e}")
    if not results:
        return

    labels = {"spacy": "regex + spaCy (baseline)", "transformer": "regex + transformer"}
    cols = list(results)
    lines = [f"# PrivacyGuard evaluation ({args.docs} synthetic documents, seed 42)\n",
             "## Strict detection F1 per entity type (value AND type must match)\n",
             "| Entity | " + " | ".join(labels[c] for c in cols) + " |",
             "|---|" + "---|" * len(cols)]
    for t in TYPES:
        row = [f"{prf(results[c]['tp'][t], results[c]['fp'][t], results[c]['fn'][t])[2]:.2f}" for c in cols]
        lines.append(f"| {t} | " + " | ".join(row) + " |")
    overall = []
    for c in cols:
        r = results[c]
        overall.append("{:.2f} / {:.2f} / {:.2f}".format(*prf(sum(r['tp'].values()), sum(r['fp'].values()), sum(r['fn'].values()))))
    lines.append("| **Overall P / R / F1** | " + " | ".join(overall) + " |")
    lines += ["", "## Privacy outcome\n",
              "| Metric | " + " | ".join(labels[c] for c in cols) + " |", "|---|" + "---|" * len(cols),
              "| Lenient recall (value detected as anything) | " + " | ".join(f"{results[c]['detected'] / results[c]['total']:.1%}" for c in cols) + " |",
              "| Leakage rate (value still readable after protection) | " + " | ".join(f"{results[c]['leaked'] / results[c]['total']:.1%}" for c in cols) + " |"]
    lines += ["", "## Leakage by type (leaked / total)\n",
              "| Entity | " + " | ".join(labels[c] for c in cols) + " |", "|---|" + "---|" * len(cols)]
    for t in TYPES:
        lines.append(f"| {t} | " + " | ".join(f"{results[c]['leak'][t][0]}/{results[c]['leak'][t][1]}" for c in cols) + " |")
    for c in cols:
        if results[c]["sims"]:
            lines.append(f"\nSemantic similarity ({labels[c]}): mean {statistics.mean(results[c]['sims']):.3f}")
    report = "\n".join(lines)
    print("\n" + report)
    open("evaluation_report.md", "w", encoding="utf-8").write(report)


if __name__ == "__main__":
    main()
