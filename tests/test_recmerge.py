import datetime as dt

from recmerge import check, gen

D = dt.date


def test_dob_formats_and_ocr_repair():
    d = D(1987, 3, 11)
    for s in ("1987-03-11", "03/11/1987", "11-Mar-1987", "Mar 11, 1987"):
        assert check.parse_dob(s)[0] == d
    assert check.parse_dob("O3/ll/1987") == (d, True)


def test_identity_swapped_dob_goes_to_review_not_include():
    doc = {"name": "SMITH, JORDAN A", "dob": "11/03/1987"}
    assert check.identity(doc, "Jordan A. Smith", D(1987, 3, 11))[0] == "REVIEW"
    assert check.identity({"name": "SMITH, JORDAN A", "dob": "01/05/1960"}, "Jordan A. Smith", D(1987, 3, 11))[0] == "EXCLUDE"


def test_brand_generic_and_units_merge_to_one_line():
    mk = lambda src, name, dose, asof: {"src": src, "kind": "med", "name": name, "dose": dose, "freq": "BID",
                                        "asof": asof, "status": "active"}
    docs = [{"name": "Jordan A. Smith", "dob": "1987-03-11", "who": "true", "records": [
        mk("epic", "Synthroid", "50 mcg", D(2026, 5, 1)), mk("athena", "LEVOTHYROXINE", "0.05 mg", D(2026, 5, 2))]}]
    r = check.assemble(docs, "Jordan A. Smith", D(1987, 3, 11))
    assert list(r["meds"]) == ["levothyroxine"] and not r["conflicts"]


def test_old_dose_is_history_recent_dose_is_conflict():
    mk = lambda dose, asof: {"src": "a", "kind": "med", "name": "metformin", "dose": dose, "freq": "BID", "asof": asof, "status": "active"}
    base = {"name": "Jordan A. Smith", "dob": "1987-03-11", "who": "true"}
    old = check.assemble([dict(base, records=[mk("500 mg", D(2025, 1, 1)), mk("1000 mg", D(2026, 5, 1))])], "Jordan A. Smith", D(1987, 3, 11))
    new = check.assemble([dict(base, records=[mk("500 mg", D(2026, 4, 25)), mk("1000 mg", D(2026, 5, 1))])], "Jordan A. Smith", D(1987, 3, 11))
    assert not old["conflicts"] and new["conflicts"] == {"metformin"}


def test_generator_labels_are_consistent():
    docs, tr = gen.make_patient(7)
    assert all(docs[i]["who"] == "wrong" for i in tr["wrong_docs"])
    assert len(tr["gaps"]) == 2
