# AlphaX Lab

Lab consumable consumption for ERPNext v15, integrated with Plasma pharma invoicing.

Version 0.1.0

---

## What it does

Plasma sends test-level invoice lines only (`CBC`, `LFT`, `Urine Routine`). ERPNext
receives them as-is. The billing document remains an exact mirror of what Plasma
billed: no injected lines, no zero-rate rows, no Packed Items, nothing extra in the
ZATCA XML or on the printed invoice.

Consumption is booked separately as a Material Issue Stock Entry on submit, linked
back to the source document, and reversed on cancel.

### Three tiers, one plan

| Tier | Examples | Frequency |
|---|---|---|
| Venipuncture kit | needle, cotton, alcohol swab, gloves, plaster | once per document |
| Sample container | EDTA tube, serum tube, urine cup | once per distinct sample type |
| Test consumables | reagents, cuvettes, controls, slides | per test line × line qty |

Tiers 1 and 2 exist because one blood draw serves every test on the invoice. Putting
a needle in each test's consumable list would consume three needles for a three-test
panel drawn once.

All three tiers are defined the same way: an Item carrying a **Lab Consumables** child
table. The venipuncture kit and each container are ordinary Items with that table
filled in and nothing else.

---

## Install

```bash
bench get-app alphax_lab <repo-url>
bench --site <site> install-app alphax_lab
bench --site <site> migrate
```

`after_install` and `after_migrate` are idempotent. They create the custom fields,
seed six standard sample types, and initialise settings.

---

## Setup

1. **Warehouse** — create `Lab Store` and set it in Lab Consumption Settings.
2. **Consumable items** — needles, cotton, tubes, reagents. Maintain Stock = 1.
   Turn on Has Batch No plus Has Expiry Date only for reagents where expiry
   genuinely matters. Batching cheap consumables costs you time and buys nothing.
3. **Venipuncture kit item** — a non-stock Item, e.g. `KIT-VENIPUNCTURE`, with its
   Lab Consumables table listing needle 1, cotton 2, swab 1, gloves 1, plaster 1.
   Set it in Settings.
4. **Container items** — one non-stock Item per container, e.g. `CONT-EDTA` with
   Lab Consumables holding the EDTA tube ×1. Link each to its Lab Sample Type.
5. **Test items** — `LAB-CBC` etc. Maintain Stock = 0, Is Sales Item = 1. Fill the
   Lab Consumables table with reagents only. **Do not create a Product Bundle** for
   these; the Plasma Test Map validator rejects that, because a bundle would consume
   through Packed Items as well and double count.
6. **Plasma Test Map** — one row per Plasma test name, linking to the item, its
   sample type, and whether it needs a draw.
7. **Item group** — put test items in `Lab Tests` and list that group in Settings.
   Any line in a listed group without an active map will be rejected on validate,
   so an unconfigured test can never post silently with zero consumption.
8. Turn on **Enabled**.

### Document scope

Enable `Consume on Sales Invoice` **or** `Consume on Delivery Note`, not both,
unless you are certain a visit only ever produces one of them. Two enabled document
types against the same visit consume twice.

---

## Integration contract

Post the Plasma invoice to ERPNext with test lines only:

```json
POST /api/resource/Sales Invoice
{
  "customer": "Walk-in Patient",
  "plasma_ref": "PLS-10023",
  "posting_date": "2026-08-30",
  "posting_time": "10:42:00",
  "set_posting_time": 1,
  "items": [
    { "item_code": "LAB-CBC",   "qty": 1, "rate": 45 },
    { "item_code": "LAB-LFT",   "qty": 1, "rate": 90 }
  ]
}
```

- `plasma_ref` is unique. A retried webhook fails on duplicate rather than
  consuming twice. This is the real idempotency guard.
- Resolve Plasma test names to `item_code` through Plasma Test Map before posting.
  An unmapped name should park in your staging queue, not auto-create an Item.
- Stage before posting. Hold the payload in a queue doctype and let a background
  job create and submit. If the lab store is short on cotton, a synchronous design
  fails Plasma's API call; a queued design leaves a retryable row.
- Credit notes post as `is_return: 1`. The app books a Material Receipt back into
  the lab store.

### Preview endpoint

```
alphax_lab.lab.consumption.preview_plan(doctype, name)
```

Returns the computed plan without posting. Useful for a client-script button and
for support triage.

---

## Reporting

**Lab Consumption Variance** splits lab store outflow into attributed (booked by
this app against a sales document) and unattributed (QC runs, calibration,
re-draws, breakage, expired write-offs, manual issues).

Watch the unattributed share. A small stable percentage is normal and healthy. A
rising one means the per-document model has drifted from bench reality, usually
because same-day add-on invoices are re-issuing venipuncture kits, or because QC
consumption has grown.

---

## Known trade-offs

**Same-day add-ons.** Scope is per-document by design. An add-on test invoiced
after the draw consumes a second venipuncture kit. If add-ons are routine, this
becomes a standing overstatement on needles, cotton and tubes. Measure it in the
variance report before deciding whether to solve it; the fix is a same-day
patient-level dedupe, which trades away statelessness and introduces a race
between concurrent webhooks.

**Gross margin per test.** Consumption hits an expense account through a Material
Issue rather than COGS on the invoice, so ERPNext's stock-linked profitability
reports will not show lab margin. A custom report joining Stock Entry back to its
source document is needed if finance wants per-test margin.

**Batch returns.** A credit note for a batched reagent books a Material Receipt
without a batch, which ERPNext will reject. Reagents are rarely returned in
practice; if they are, handle the reversal manually.

**Line qty above 1.** Reagents scale with line qty; the venipuncture kit and
containers do not. That is correct when qty 2 means a repeat run on the same
sample, and wrong if Plasma ever puts two patients on one invoice. Confirm which
Plasma means before go-live.

**Non-billable consumption.** QC, calibration and wastage are issued manually as
ordinary Stock Entries. They are deliberately outside this app's scope and show up
as unattributed in the variance report.

---

## Test plan before go-live

1. Single test, single sample type. One needle, one tube, correct reagents.
2. Three tests, one draw, two sample types. One needle, two tubes.
3. Cancel the invoice. Stock Entry cancels, stock returns.
4. Amend and resubmit. Exactly one active Stock Entry remains.
5. Duplicate `plasma_ref`. Insert fails, no stock movement.
6. Batched reagent with two open batches, one expiring sooner. Nearest expiry is
   picked, and the row splits when one batch cannot cover the qty.
7. Expired batch only. Document is blocked with a clear message.
8. Lab store short on cotton. Document is blocked when `block_on_shortage` is on,
   and logged when off.
9. Credit note. Material Receipt returns unbatched consumables to stock.
10. Test item in `Lab Tests` with no map. Validate rejects it.

---

## House rules

Run `python tests/test_consumption_plan.py` for the plan builder. It stubs frappe
with fixture data, so it needs no bench and no database and can run in CI from a
clean checkout.

Run `python verify_tree.py` before every commit. It checks file structure, doctype
module ownership, hook wiring, tab indentation, absence of Server Script fixtures,
and that the Product Bundle double-consumption guard is still in place.
