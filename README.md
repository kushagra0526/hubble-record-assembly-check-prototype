# recmerge: checks on an assembled patient record

Hubble's site says its assembled record hands back "every value carries the system it came from", pulled from EHRs, payers and HIE networks, plus voice and browser agents for the long tail (https://hubble.ai/). When records arrive from several systems and from faxes, three things have to be right before one record goes to a downstream AI agent: the document belongs to this patient, the same fact from two sources is one line, and conflicts and missing pieces are shown rather than hidden. This prototype checks those three on synthetic data.

## What it does
For one verified patient (name + DOB) and a set of source documents:
- **Identity per document:** `INCLUDE` / `REVIEW` / `EXCLUDE`. Name must match (LAST, FIRST and nickname forms); DOB is parsed from ISO, US, `11-Mar-1987` and `Mar 11, 1987`, with OCR repair (`O`->0, `l`->1). A DOB with day and month swapped, or one digit off, goes to `REVIEW`, never `INCLUDE`.
- **Medications:** brand -> generic, `0.05 mg` = `50 mcg`, `BID` = `twice daily`, merged into one line listing every source. Two sources that disagree within 30 days are a `CONFLICT` (both shown); an older record with a different dose is history, not a conflict.
- **Allergies:** union across sources (nothing is dropped because another source is "more complete").
- **Gaps:** a referral with no later encounter of that specialty (180 days) and a lab order with no result, each listed as something to chase.

## Results (synthetic patients, known truth)
Dev: seeds 0-99. Held-out: seeds 1000-1199 with unseen dose spellings (`0.05 mg` for levothyroxine) and look-alike documents with day/month-swapped DOBs; code and seeds committed before the first run.

| Held-out, 200 patients | take every document | exact header match | recmerge |
|---|---|---|---|
| wrong-patient documents included (134 planted) | 134 | 0 | 0 (53 held for review) |
| true documents with OCR-damaged DOB kept (92) | 92 | 0 | 92 |
| medication lines (truth 909) | 1,988 | 602 | 909 |
| true allergies lost (293) | 0 | 180 | 0 |
| allergies that belong to another patient | 134 | 0 | 0 |
| dose/status conflicts flagged (88 planted) | 0 | n/a | 88, 0 false |
| referral/lab gaps found (400 planted) | 0 | n/a | 400, 0 false |

Dev gave the same pattern (0 wrong included of 74, 450/450 medications, 48/48 conflicts, 200/200 gaps).

## Read this before believing the table
It got everything on the first run. That says more about my generator than about the checker: the generator and checker share the same brand and allergy name tables and the same OCR noise model (O/l only), and the planted problems are exactly the ones the checker looks for. A real record will have drug names, units, document layouts and identity noise that are not in these tables; unmapped drug names are listed under `unmapped` instead of being merged, and a DOB misread in any way other than O/l or one digit goes to `REVIEW` or `EXCLUDE`, which would hold true documents. "Exact header match" is a strawman baseline. Nothing here uses real patient data, any Hubble API, or any real health record.

## Run it (3 commands)
```
pip install pytest
python -m pytest -q tests
python -m recmerge.run
```
Standard library only. 5 tests.

Unofficial prototype by Kushagra Pratap Singh. Not affiliated with Hubble.
