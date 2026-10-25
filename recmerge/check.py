"""Assemble one patient record from several source documents.

Per document: INCLUDE / REVIEW / EXCLUDE by identity. Per medication: merge to
one line with every source, flag a CONFLICT when two sources disagree within
30 days (older disagreement is just history). Allergies are a union. Referrals
and lab orders with no later encounter/result are listed as GAPs to chase.
"""
import datetime as dt
import re

from .gen import BRANDS, ALLERGY

GENERIC = {b.lower(): g for g, bs in BRANDS.items() for b in bs} | {g: g for g in BRANDS}
ALLERGEN = {s.lower(): a for a, ss in ALLERGY.items() for s in ss} | {a: a for a in ALLERGY}
NICK = {"bob": "robert", "liz": "elizabeth", "will": "william", "jon": "jonathan"}
FREQ = {"daily": "daily", "once daily": "daily", "qd": "daily", "1x/day": "daily",
        "bid": "bid", "twice daily": "bid", "2x/day": "bid"}
FIX = str.maketrans({"O": "0", "o": "0", "l": "1", "I": "1", "S": "5"})
MONTHS = {m: i for i, m in enumerate("jan feb mar apr may jun jul aug sep oct nov dec".split(), 1)}


def parse_dob(s):
    """-> date or None. Slash dates are MM/DD/YYYY (US sources). Returns (date, repaired)."""
    for fixed, txt in ((False, s), (True, s.translate(FIX))):
        m = re.fullmatch(r"(\d{4})-(\d\d)-(\d\d)", txt)
        if m:
            y, mo, d = map(int, m.groups())
        elif (m := re.fullmatch(r"(\d\d)/(\d\d)/(\d{4})", txt)):
            mo, d, y = map(int, m.groups())
        elif (m := re.fullmatch(r"(\d\d)-([A-Za-z]{3})-(\d{4})", s)):
            d, y, mo = int(m[1]), int(m[3]), MONTHS.get(m[2].lower(), 0)
        elif (m := re.fullmatch(r"([A-Za-z]{3}) (\d\d), (\d{4})", s)):
            mo, d, y = MONTHS.get(m[1].lower(), 0), int(m[2]), int(m[3])
        else:
            continue
        try:
            return dt.date(y, mo, d), fixed
        except ValueError:
            continue
    return None, False


def person_key(s):
    first, last = (re.sub(r"[.,]", " ", s).split() + [""])[:2]
    if "," in s:
        last, first = re.sub(r"[.,]", " ", s).split()[:2]
    first = NICK.get(first.lower(), first.lower())
    last = last.lower() if "," in s else re.sub(r"[.,]", " ", s).split()[-1].lower()
    return first, last


def identity(doc, patient_name, patient_dob):
    """Reference identity comes from the requesting patient's verified profile."""
    d, repaired = parse_dob(doc["dob"])
    if person_key(doc["name"]) != person_key(patient_name):
        return "EXCLUDE", "name differs"
    if d is None:
        return "REVIEW", "unreadable DOB"
    if d == patient_dob:
        return "INCLUDE", "OCR-repaired DOB" if repaired else "match"
    if (d.month, d.day) == (patient_dob.day, patient_dob.month) and d.year == patient_dob.year:
        return "REVIEW", "DOB day/month swapped"
    diff = sum(a != b for a, b in zip(d.isoformat(), patient_dob.isoformat()))
    return ("REVIEW", "DOB differs by one digit") if diff <= 1 else ("EXCLUDE", "different DOB")


def dose_mg(s):
    m = re.search(r"([\d.]+)\s*(mcg|mg|g)\b", s, re.I)
    v, u = float(m[1]), m[2].lower()
    return round(v / 1000 if u == "mcg" else v * 1000 if u == "g" else v, 4)


def generic(name):
    return GENERIC.get(name.lower())


def assemble(docs, patient_name, patient_dob):
    inc, review, excl = [], [], []
    for i, d in enumerate(docs):
        v, why = identity(d, patient_name, patient_dob)
        {"INCLUDE": inc, "REVIEW": review, "EXCLUDE": excl}[v].append((i, why))
    recs = [r for i, _ in inc for r in docs[i]["records"]]
    meds, conflicts, allergies, unmapped = {}, [], {}, []
    by_g = {}
    for r in recs:
        if r["kind"] == "med":
            g = generic(r["name"])
            (by_g.setdefault(g, []) if g else unmapped).append(r)
    for g, rs in by_g.items():
        rs = sorted(rs, key=lambda r: r["asof"])
        last = rs[-1]
        sig = lambda r: (dose_mg(r["dose"]), FREQ[r["freq"].lower()], r["status"])
        seen = {last["src"]}
        for r in rs[:-1]:
            seen.add(r["src"])
            if sig(r) != sig(last) and (last["asof"] - r["asof"]).days <= 30:
                conflicts.append(g)
        meds[g] = {"dose_mg": sig(last)[0], "freq": sig(last)[1], "status": last["status"], "sources": sorted(seen)}
    for r in recs:
        if r["kind"] == "allergy":
            a = ALLERGEN.get(r["name"].lower(), r["name"].lower())
            allergies.setdefault(a, set()).add(r["src"])
    gaps = set()
    for r in recs:
        if r["kind"] == "referral" and not any(
                x["kind"] == "enc" and x["spec"] == r["spec"] and 0 <= (x["asof"] - r["asof"]).days <= 180 for x in recs):
            gaps.add(("referral", r["spec"]))
        if r["kind"] == "lab_order" and not any(
                x["kind"] == "lab_result" and x["name"] == r["name"] and x["asof"] >= r["asof"] for x in recs):
            gaps.add(("lab", r["name"]))
    return {"meds": meds, "conflicts": set(conflicts), "allergies": allergies, "gaps": gaps, "unmapped": unmapped,
            "include": inc, "review": review, "exclude": excl}


def naive(docs):
    """Baseline: take every document as is; exact-string med lines; no checks."""
    lines = {(r["name"], r["dose"], r["freq"]) for d in docs for r in d["records"] if r["kind"] == "med"}
    allergies = {r["name"] for d in docs for r in d["records"] if r["kind"] == "allergy"}
    return {"med_lines": len(lines), "allergies": allergies, "include": list(range(len(docs)))}


def exact(docs, patient_name_str, patient_dob_iso):
    """Baseline: keep a document only if its header equals the profile strings exactly; merge on exact strings."""
    keep = [d for d in docs if d["name"] == patient_name_str and d["dob"] == patient_dob_iso]
    lines = {(r["name"], r["dose"], r["freq"]) for d in keep for r in d["records"] if r["kind"] == "med"}
    allergies = {r["name"] for d in keep for r in d["records"] if r["kind"] == "allergy"}
    return {"med_lines": len(lines), "allergies": allergies, "include": keep}
