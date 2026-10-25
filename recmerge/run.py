import datetime as dt
import json
import sys

from . import check, gen


def profile(docs):
    """The requesting patient's verified profile = the EHR (epic) header."""
    d = docs[0]
    return d["name"], check.parse_dob(d["dob"])[0]


def score(seeds, held_out):
    t = dict(patients=0, wrong=0, wrong_in_naive=0, wrong_in_exact=0, wrong_in_mine=0, wrong_held=0,
             noisy_true=0, noisy_true_in_mine=0, noisy_true_in_exact=0, true_docs_not_in_mine=0,
             med_truth=0, med_lines_naive=0, med_lines_exact=0, med_lines_mine=0, med_missing_mine=0, med_wrong_mine=0,
             allergy_truth=0, allergy_lost_exact=0, allergy_lost_mine=0, allergy_extra_naive=0, allergy_extra_mine=0,
             conf_truth=0, conf_found=0, conf_false=0, gap_truth=0, gap_found=0, gap_false=0)
    for s in seeds:
        docs, tr = gen.make_patient(s, held_out)
        name, dob = profile(docs)
        r = check.assemble(docs, name, dob)
        nv, ex = check.naive(docs), check.exact(docs, docs[0]["name"], docs[0]["dob"])
        inc = {i for i, _ in r["include"]}
        t["patients"] += 1
        t["wrong"] += len(tr["wrong_docs"])
        t["wrong_in_naive"] += len(tr["wrong_docs"])
        t["wrong_in_exact"] += sum(docs[i] in ex["include"] for i in tr["wrong_docs"])
        t["wrong_in_mine"] += sum(i in inc for i in tr["wrong_docs"])
        t["wrong_held"] += sum(i in {j for j, _ in r["review"]} for i in tr["wrong_docs"])
        t["noisy_true"] += len(tr["noisy_true_docs"])
        t["noisy_true_in_mine"] += sum(i in inc for i in tr["noisy_true_docs"])
        t["noisy_true_in_exact"] += sum(docs[i] in ex["include"] for i in tr["noisy_true_docs"])
        t["true_docs_not_in_mine"] += sum(d["who"] == "true" and i not in inc for i, d in enumerate(docs))
        t["med_truth"] += len(tr["meds"])
        t["med_lines_naive"] += nv["med_lines"]
        t["med_lines_exact"] += ex["med_lines"]
        t["med_lines_mine"] += len(r["meds"])
        t["med_missing_mine"] += len(set(tr["meds"]) - set(r["meds"]))
        t["med_wrong_mine"] += len(set(r["meds"]) - set(tr["meds"]))
        t["allergy_truth"] += len(tr["allergies"])
        have = {check.ALLERGEN.get(a.lower(), a.lower()) for a in ex["allergies"]}
        t["allergy_lost_exact"] += len(tr["allergies"] - have)
        t["allergy_lost_mine"] += len(tr["allergies"] - set(r["allergies"]))
        t["allergy_extra_naive"] += len({check.ALLERGEN.get(a.lower(), a.lower()) for a in nv["allergies"]} - tr["allergies"])
        t["allergy_extra_mine"] += len(set(r["allergies"]) - tr["allergies"])
        t["conf_truth"] += len(tr["conflicts"])
        t["conf_found"] += len(tr["conflicts"] & r["conflicts"])
        t["conf_false"] += len(r["conflicts"] - tr["conflicts"])
        t["gap_truth"] += len(tr["gaps"])
        t["gap_found"] += len(tr["gaps"] & r["gaps"])
        t["gap_false"] += len(r["gaps"] - tr["gaps"])
    return t


def main():
    out = {"dev": score(range(0, 100), False), "held_out": score(range(1000, 1200), True)}
    json.dump(out, open("out/result.json", "w"), indent=1)
    for k, v in out.items():
        print(k, json.dumps(v))


if __name__ == "__main__":
    main()
