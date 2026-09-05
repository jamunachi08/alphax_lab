# Lab starter catalog — Data Import files

12 tests, 32 consumables, 28 batches. No shell access needed: everything here
goes in through **Setup → Data Import**.

Import in numbered order. Each file depends on the ones before it.

---

## Before you start

Create these by hand first, or the imports will fail on missing links:

1. **Item Groups**: `Lab Tests` and `Lab Consumables`
2. **Warehouse**: `Lab Store` under your company
3. **UOM**: `Nos` (already exists in a standard install)

Then install AlphaX Lab and run `bench migrate`, so the Lab Test Consumption
doctype and the six Lab Sample Types exist.

---

## The files

| # | File | Doctype | Rows |
|---|---|---|---|
| 1 | `01_items_consumables.csv` | Item | 32 |
| 2 | `02_items_tests.csv` | Item | 12 |
| 3 | `03_batches.csv` | Batch | 28 |
| 4 | `04_lab_test_consumption.csv` | Lab Test Consumption | 12 records, 113 rows |
| 5 | `05_plasma_test_map.csv` | Plasma Test Map | 12 |
| 6 | `06_opening_stock.csv` | Stock Entry | 1 entry, 46 rows |

For each: Data Import → **Insert New Records** → pick the doctype → upload →
map is automatic since the headers are fieldnames → Start Import.

### Two files need editing first

**`06_opening_stock.csv`** has two placeholders. Find and replace before
uploading:

- `<YOUR COMPANY>` → your company name, exactly as in the Company list
- `<LAB STORE WAREHOUSE>` → your warehouse, e.g. `Lab Store - NA`

It imports as a **draft**. Open it, check the valuation rates, then submit.
Nothing enters stock until you submit.

**Check Stock Settings first.** If **Item Naming By** is set to `Naming Series`,
`item_code` is overwritten during creation and every code in these files becomes
`ITEM-0001` and so on. Set it to `Item Code` before importing files 1
and 2. You can set it back afterwards.

### Files 4 and 6 use parent/child grouping

The first row of each group carries the parent fields; continuation rows leave
them blank and fill only the child columns. Do not fill the blanks in — repeating
the parent value on every row creates one record per row instead of one record
with many child rows.

---

## What the catalog contains

**Tests** — CBC, ESR, Blood Group, FBS, HbA1c, Lipid Profile, LFT, RFT, TSH,
Vitamin D, CRP, Urine Routine.

**Consumables** — draw items (needles, butterfly, syringe, cotton, swabs, gloves,
tourniquet, plaster), containers (EDTA, SST, fluoride, citrate tubes, urine cup),
lab disposables (pipette tips, cuvettes, slides), and batched items (11 reagents,
2 controls, urine dipsticks).

**Batches** — two per batched item, one expiring within roughly two months and
one over a year out. That is deliberate: it lets you verify nearest-expiry
selection actually works rather than assuming it.

**Consumption records** — every test lists its complete set, draw items included.
Eleven of the twelve are venous draws and each carries its own needle, cotton,
swab, gloves, tourniquet and plaster. Urine Routine has no draw items.

Remember what that means: a document with CBC and LFT consumes two needles, not
one. That is the flat model working as specified. Watch the **Lab Consumption
Variance** report and, if the overstatement matters in practice, remove the draw
block from all but one test in each common panel.

---

## After importing

```
Unconfigured Lab Items    → should return nothing
Lab Test Consumables      → 12 tests with their lists and stock on hand
```

Then configure **Lab Consumption Settings**: warehouse, `Lab Tests` in Lab Item
Groups, choose Sales Invoice or Delivery Note (not both), and turn on Enabled.

Post a Delivery Note with CBC and LFT. Check the linked Stock Entry: two needles,
four cotton balls, one EDTA tube, one SST tube, and the `-A` reagent batches
picked ahead of the `-B` ones.

---

## Prices

The `rate` values on tests and the `basic_rate` values on consumables are
plausible placeholders in SAR, not quotes. Replace them with your real purchase
costs before trusting any margin or valuation figure.
