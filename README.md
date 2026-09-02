# AlphaX Lab

Lab consumable consumption, integrated with Plasma pharma invoicing.

Version 0.2.1

---

## What it does

Plasma sends test-level invoice lines only (`CBC`, `LFT`, `Urine Routine`). Those
arrive as-is. The billing document stays an exact mirror of what Plasma billed:
no injected lines, no zero-rate rows, no Packed Items, nothing extra in the ZATCA
XML or on the printed invoice.

Each test Item carries its own complete consumable list. When a document is
submitted, every mapped line's consumables are summed and issued from the lab
store as a Material Issue Stock Entry, linked back to the source document and
reversed on cancel.

Consumption is driven by the submit event, so it fires identically whether the
document was typed by a user, created through Data Import, or posted over the
REST API. Data Import only triggers it if the import submits; drafts consume
nothing until submitted.

---

## The consumable list

One child table, **Lab Consumables**, on each test Item. Define everything the
test needs, draw items included:

| Item | Qty |
|---|---|
| NEEDLE-21G | 1 |
| COTTON | 2 |
| TUBE-EDTA | 1 |
| REG-CBC | 1 |
| CTRL-CBC | 0.05 |

Quantities are per one unit sold and scale with line qty. Fractional quantities
are supported for reagents and controls, as long as the UOM does not have "Must
be Whole Number" set.

### One thing to watch

Consumables accumulate across lines. A document with CBC and LFT, each listing a
needle, consumes two needles even though the patient was drawn once. That is the
model working as specified, not a bug.

Whether it matters depends on how often multiple blood tests share an invoice.
Watch the **Lab Consumption Variance** report. If needles and tubes drift
consistently high against physical counts, the cheap fix is to list the draw
consumables on one designated test per common panel rather than on all of them.

---

## Install

```bash
bench get-app alphax_lab <repo-url>
bench --site <site> install-app alphax_lab
bench --site <site> migrate
```

`after_install` and `after_migrate` are idempotent. They create the custom
fields, seed six standard sample types, and initialise settings.

---

## Setup

1. **Warehouse** — create `Lab Store` and set it in Lab Consumption Settings.
2. **Consumable items** — needles, cotton, tubes, reagents. Maintain Stock = 1.
   Turn on Has Batch No plus Has Expiry Date only for reagents where expiry
   genuinely matters. Batching cheap consumables costs time and buys nothing.
3. **Test items** — `LAB-CBC` etc. Maintain Stock = 0, Is Sales Item = 1. Fill
   the Lab Consumables table with the complete list for that test. **Do not
   create a Product Bundle** for these; the Plasma Test Map validator rejects
   that, because a bundle would consume through Packed Items as well and double
   count.
4. **Plasma Test Map** — one row per Plasma test name, linking to its item.
   Sample type is optional classification for reporting.
5. **Item group** — put test items in `Lab Tests` and list that group in
   Settings. See "Unconfigured items" below for what happens to a line in that
   group that is not set up.
6. Turn on **Enabled**.

After setup, and after any bulk item import, run the **Unconfigured Lab Items**
report. It lists every item that would consume nothing if sold.

### Unconfigured items

An item in a lab item group consumes nothing if it has no active Plasma Test Map,
or if it has a map but an empty Lab Consumables table. The second case hides well:
the item looks configured from the list view.

`Unconfigured Item Action` in Settings controls what happens:

| Setting | On save | On submit |
|---|---|---|
| Warn Only | warning | warning |
| **Block on Submit** (default) | warning | blocked |
| Block on Save | blocked | blocked |

Block on Submit is the right default for a lab. Reception can save a
half-finished document and come back to it, but nothing can post that would
consume no stock — the failure this app exists to prevent, and one that is
invisible after the fact.

### Document scope

Enable `Consume on Sales Invoice` **or** `Consume on Delivery Note`, not both,
unless a visit only ever produces one of them. Two enabled document types
against the same visit consume twice.

---

## Integration contract

Post the Plasma invoice with test lines only:

```json
POST /api/resource/Sales Invoice
{
  "customer": "Walk-in Patient",
  "plasma_ref": "PLS-10023",
  "posting_date": "2026-08-30",
  "posting_time": "10:42:00",
  "set_posting_time": 1,
  "items": [
    { "item_code": "LAB-CBC", "qty": 1, "rate": 45 },
    { "item_code": "LAB-LFT", "qty": 1, "rate": 90 }
  ]
}
```

- `plasma_ref` is unique. A retried webhook fails on duplicate rather than
  consuming twice. This is the real idempotency guard.
- Resolve Plasma test names to `item_code` through Plasma Test Map before
  posting. An unmapped name should park in your staging queue, never
  auto-create an Item.
- Stage before posting. Hold the payload in a queue doctype and let a background
  job create and submit. If the lab store is short on cotton, a synchronous
  design fails Plasma's API call; a queued design leaves a retryable row.
- Credit notes post as `is_return: 1`. A Material Receipt returns the
  consumables to the lab store.

### Preview endpoint

```
alphax_lab.lab.consumption.preview_plan(doctype, name)
```

Returns the computed plan without posting. Useful for a client-script button and
for support triage.

---

## Reporting

**Unconfigured Lab Items** lists every item in a lab item group that would consume
nothing if sold, with the reason and the fix for each. Run it after setup and
after any bulk item import.

**Lab Consumption Variance** splits lab store outflow into attributed (booked by
this app against a sales document) and unattributed (QC runs, calibration,
re-draws, breakage, expired write-offs, manual issues).

Watch the unattributed share. A small stable percentage is normal. A rising one
means the consumable lists have drifted from what the bench actually uses.

---

## Known trade-offs

**Shared draw consumables.** Covered above. Multiple blood tests on one document
consume one draw kit each.

**Gross margin per test.** Consumption hits an expense account through a Material
Issue rather than COGS on the invoice, so stock-linked profitability reports will
not show lab margin. A custom report joining Stock Entry back to its source
document is needed if finance wants per-test margin.

**Batch returns.** A credit note for a batched reagent books a Material Receipt
without a batch, which will be rejected. Reagents are rarely returned; if they
are, handle the reversal manually.

**Non-billable consumption.** QC, calibration and wastage are issued manually as
ordinary Stock Entries. They are deliberately outside this app's scope and show
up as unattributed in the variance report.

---

## Test plan before go-live

1. Single test. Consumables match the item's list exactly.
2. Two blood tests on one document. Shared consumables accumulate as expected.
3. Line qty 2. Everything doubles.
4. Cancel the document. Stock Entry cancels, stock returns.
5. Amend and resubmit. Exactly one active Stock Entry remains.
6. Duplicate `plasma_ref`. Insert fails, no stock movement.
7. Batched reagent with two open batches, one expiring sooner. Nearest expiry is
   picked, and the row splits when one batch cannot cover the qty.
8. Expired batch only. Document is blocked with a clear message.
9. Lab store short on cotton. Blocked when `block_on_shortage` is on, logged
   when off.
10. Credit note. Material Receipt returns unbatched consumables to stock.
11. Test item in `Lab Tests` with no map. Draft saves with a warning, submit is
    blocked.
12. Mapped test item with an empty Lab Consumables table. Same treatment.
13. Unconfigured Lab Items report lists both of the above.
14. Data Import of submitted documents. Consumption fires per document.

---

## House rules

```bash
python tests/test_consumption_plan.py   # plan builder, no bench or DB needed
python verify_tree.py                   # structural guard, run before commit
```

`verify_tree.py` checks file structure, doctype module ownership, hook wiring,
tab indentation, absence of Server Script fixtures, the frappe-dependencies
block that Frappe Cloud requires, the Product Bundle double-consumption guard,
and that no vendor name has crept back into user-facing strings.
