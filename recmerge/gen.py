"""Synthetic multi-source patient records with known truth.

One patient, three sources (epic, athena, fax). Every fax/portal document has a
header (name, DOB) and records. Planted problems have a known label.
"""
import datetime as dt
import random

D = dt.date
BRANDS = {"atorvastatin": ["Lipitor"], "metformin": ["Glucophage"], "lisinopril": ["Zestril", "Prinivil"],
          "levothyroxine": ["Synthroid"], "amlodipine": ["Norvasc"], "simvastatin": ["Zocor"],
          "sertraline": ["Zoloft"], "omeprazole": ["Prilosec"]}
DOSES = {"atorvastatin": [10, 20, 40, 80], "metformin": [500, 850, 1000], "lisinopril": [5, 10, 20, 40],
         "levothyroxine": [25, 50, 75, 100], "amlodipine": [2.5, 5, 10], "simvastatin": [10, 20, 40],
         "sertraline": [25, 50, 100], "omeprazole": [20, 40]}
FREQS = {"daily": ["daily", "once daily", "QD", "1x/day"], "bid": ["BID", "twice daily", "2x/day"]}
ALLERGY = {"penicillin": ["Penicillin", "PCN", "penicillins"], "sulfa": ["Sulfa", "sulfonamides", "SMX-TMP"],
           "latex": ["Latex"], "codeine": ["Codeine"], "iodine": ["Iodine contrast", "iodinated contrast"]}
SPEC = ["cardiology", "endocrinology", "nephrology", "neurology"]
LABS = ["HbA1c", "lipid panel", "TSH", "creatinine"]
FIRST = ["Jordan", "Priya", "Marcus", "Elena", "Wei", "Amara", "Tomas", "Hana", "Diego", "Noor"]
LAST = ["Smith", "Patel", "Nguyen", "Garcia", "Okafor", "Kim", "Rossi", "Haddad", "Larsen", "Silva"]
TODAY = D(2026, 6, 1)


def dob_str(d, fmt):
    return {"iso": d.isoformat(), "us": d.strftime("%m/%d/%Y"), "dmy": d.strftime("%d-%b-%Y"),
            "long": d.strftime("%b %d, %Y")}[fmt]


def name_str(first, mi, last, style):
    return {"fl": f"{first} {mi}. {last}", "lf": f"{last.upper()}, {first.upper()} {mi}", "f_l": f"{first} {last}"}[style]


def dose_str(g, mg, rng, new_forms):
    unit = "mcg" if g == "levothyroxine" else "mg"
    v = mg
    forms = [f"{v:g} {unit}", f"{v:g}{unit}", f"{v:g} {unit.upper()}"]
    if new_forms and unit == "mcg":
        forms.append(f"{v / 1000:g} mg")
    return rng.choice(forms)


def med_name(g, rng, brand_p=0.35):
    return rng.choice(BRANDS[g]) if rng.random() < brand_p else rng.choice([g, g.upper(), g.capitalize()])


def rec_med(src, g, mg, freq, asof, status, rng, new_forms):
    return {"src": src, "kind": "med", "name": med_name(g, rng), "dose": dose_str(g, mg, rng, new_forms),
            "freq": rng.choice(FREQS[freq]), "asof": asof, "status": status}


def make_patient(seed, held_out=False):
    """held_out=True: unseen dose spellings, DOB day/month swap look-alikes, fax OCR noise."""
    rng = random.Random(seed)
    first, last, mi = rng.choice(FIRST), rng.choice(LAST), rng.choice("ABCDEJKMRS")
    dob = D(rng.randint(1950, 2002), rng.randint(1, 12), rng.randint(1, 12))  # day <= 12 so swap is a real date
    base = TODAY - dt.timedelta(days=rng.randint(10, 60))
    docs = {s: {"src": s, "who": "true", "records": []} for s in ("epic", "athena", "fax")}
    for s, style, fmt in (("epic", "fl", "iso"), ("athena", "lf", "us"), ("fax", rng.choice(["fl", "lf", "f_l"]),
                                                                           rng.choice(["us", "dmy", "long"]))):
        docs[s]["name"] = name_str(first, mi, last, style)
        docs[s]["dob"] = dob_str(dob, fmt)
    truth = {"conflicts": set(), "gaps": set(), "allergies": set(), "meds": {}, "wrong_docs": [], "noisy_true_docs": []}
    gens = rng.sample(list(DOSES), rng.randint(3, 6))
    planted = rng.sample(["dose", "status", "stale"], k=rng.randint(0, 2))
    for i, g in enumerate(gens):
        mg = rng.choice(DOSES[g])
        freq = rng.choice(list(FREQS))
        where = rng.sample(["epic", "athena", "fax"], rng.choice([1, 2, 2, 3]))
        status = "active"
        truth["meds"][g] = (mg, freq, status)
        for s in where:
            docs[s]["records"].append(rec_med(s, g, mg, freq, base - dt.timedelta(days=rng.randint(0, 10)), status, rng, held_out))
        if i < len(planted) and len(where) >= 2:
            a, b = where[0], where[1]
            if planted[i] == "dose":  # same week, different dose -> cannot both be right
                other = rng.choice([d for d in DOSES[g] if d != mg])
                r = [x for x in docs[b]["records"] if x["name"] and x["asof"]][-1]
                docs[b]["records"][-1] = rec_med(b, g, other, freq, r["asof"], "active", rng, held_out)
                truth["conflicts"].add(g)
            elif planted[i] == "status":
                r = docs[b]["records"][-1]
                docs[b]["records"][-1] = rec_med(b, g, mg, freq, r["asof"], "stopped", rng, held_out)
                truth["conflicts"].add(g)
            else:  # stale: older record with an old dose, >60 days earlier -> history, not a conflict
                old = rng.choice([d for d in DOSES[g] if d != mg])
                docs[b]["records"][-1] = rec_med(b, g, old, freq, base - dt.timedelta(days=rng.randint(90, 400)), "active", rng, held_out)
    for a in rng.sample(list(ALLERGY), rng.randint(1, 2)):
        truth["allergies"].add(a)
        for s in rng.sample(["epic", "athena", "fax"], rng.choice([1, 1, 2])):
            docs[s]["records"].append({"src": s, "kind": "allergy", "name": rng.choice(ALLERGY[a]), "asof": base})
    for spec in rng.sample(SPEC, 2):  # one referral that was seen, one that was not
        rd = base - dt.timedelta(days=rng.randint(40, 120))
        docs["epic"]["records"].append({"src": "epic", "kind": "referral", "spec": spec, "asof": rd})
    r_seen, r_lost = [r for r in docs["epic"]["records"] if r["kind"] == "referral"]
    docs[rng.choice(["athena", "fax"])]["records"].append(
        {"src": "athena", "kind": "enc", "spec": r_seen["spec"], "asof": r_seen["asof"] + dt.timedelta(days=rng.randint(5, 40))})
    truth["gaps"].add(("referral", r_lost["spec"]))
    for lab, has_result in zip(rng.sample(LABS, 2), (True, False)):
        od = base - dt.timedelta(days=rng.randint(20, 60))
        docs["epic"]["records"].append({"src": "epic", "kind": "lab_order", "name": lab, "asof": od})
        if has_result:
            docs["athena"]["records"].append({"src": "athena", "kind": "lab_result", "name": lab, "asof": od + dt.timedelta(days=3)})
        else:
            truth["gaps"].add(("lab", lab))
    out = [docs["epic"], docs["athena"], docs["fax"]]
    if rng.random() < 0.5:  # a second fax: the same patient, header digits damaged by OCR (O for 0, l for 1)
        d2 = {"src": "fax", "who": "true", "name": name_str(first, mi, last, "f_l"), "records": []}
        s = dob_str(dob, "us").replace("0", "O").replace("1", "l")
        d2["dob"] = s
        g = rng.choice(gens)
        d2["records"].append(rec_med("fax", g, truth["meds"][g][0], truth["meds"][g][1], base, "active", rng, held_out))
        out.append(d2)
        truth["noisy_true_docs"].append(len(out) - 1)
    if rng.random() < 0.7:  # a look-alike patient's document sent by mistake
        if held_out and rng.random() < 0.5:
            wd = D(dob.year, dob.day, dob.month)  # same name, day and month swapped
            if wd == dob:
                wd = D(dob.year, dob.month, 28)
        else:
            wd = D(rng.randint(1950, 2002), rng.randint(1, 12), rng.randint(1, 28))
            if wd == dob:
                wd = D(wd.year - 1, wd.month, wd.day)
        w = {"src": "fax", "who": "wrong", "name": name_str(first, mi, last, "lf"), "dob": dob_str(wd, "us"), "records": [
            rec_med("fax", rng.choice([g for g in DOSES if g not in gens] or ["sertraline"]),
                    5, "daily", base, "active", rng, held_out),
            {"src": "fax", "kind": "allergy", "name": rng.choice([x for a, v in ALLERGY.items() if a not in truth["allergies"] for x in v]), "asof": base}]}
        out.append(w)
        truth["wrong_docs"].append(len(out) - 1)
    return out, truth
