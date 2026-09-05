# Copyright (c) 2026, Neotec Integrated Solutions and contributors
# For license information, please see license.txt

"""Batch allocation for lab consumable issues.

v15 stores batch quantities in one of two places depending on how the stock was
received:

    legacy  Stock Ledger Entry.batch_no is populated directly
    bundle  Stock Ledger Entry.batch_no is NULL and the detail sits in
            Serial and Batch Entry rows under a Serial and Batch Bundle

Data Import, older documents, and `use_serial_batch_fields` produce the first.
The standard v15 UI produces the second. Reading only one of them makes real
stock invisible and reports a phantom shortage, so availability is summed across
both.

Issuing always uses the legacy fields, `use_serial_batch_fields = 1` plus
`batch_no` on the Stock Entry Detail row, and the bundle is built on submit.

The allocator returns one row per (batch, qty) pair, so a single requirement may
expand into several Stock Entry Detail rows when no one batch can cover it.
"""

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate

FAR_FUTURE = "2999-12-31"


def allocate(item_code, warehouse, qty, posting_date=None, strategy="Nearest Expiry", allow_expired=False):
	"""Split `qty` of `item_code` across available batches.

	Returns (allocations, shortfall) where allocations is a list of dicts
	[{"qty": float, "batch_no": str | None}, ...]. Non-batched items return a
	single row with batch_no None and skip the batch lookup entirely.
	"""
	qty = flt(qty)
	if qty <= 0:
		return [], 0.0

	if not is_batched(item_code):
		return [{"qty": qty, "batch_no": None}], 0.0

	posting_date = getdate(posting_date or nowdate())
	batches = _candidate_batches(item_code, warehouse, posting_date, strategy, allow_expired)

	allocations = []
	remaining = qty

	for batch in batches:
		if remaining <= 0:
			break
		take = min(remaining, batch["available"])
		if take <= 0:
			continue
		allocations.append({"qty": take, "batch_no": batch["name"]})
		remaining -= take

	return allocations, max(remaining, 0.0)


def is_batched(item_code):
	return bool(frappe.get_cached_value("Item", item_code, "has_batch_no"))


# ---------------------------------------------------------------------------
# availability
# ---------------------------------------------------------------------------

def batch_availability(item_code, warehouse, posting_date=None):
	"""Map of batch_no -> qty in `warehouse`, summed across both storage paths."""
	posting_date = getdate(posting_date or nowdate())
	totals = {}

	for source in (_legacy_quantities, _bundle_quantities):
		for batch_no, qty in source(item_code, warehouse, posting_date).items():
			totals[batch_no] = flt(totals.get(batch_no, 0)) + flt(qty)

	return totals


def _legacy_quantities(item_code, warehouse, posting_date):
	rows = frappe.db.sql(
		"""
		select sle.batch_no as batch_no, sum(sle.actual_qty) as qty
		from `tabStock Ledger Entry` sle
		where sle.item_code = %(item_code)s
			and sle.warehouse = %(warehouse)s
			and sle.is_cancelled = 0
			and ifnull(sle.batch_no, '') != ''
			and sle.posting_date <= %(posting_date)s
		group by sle.batch_no
		""",
		{"item_code": item_code, "warehouse": warehouse, "posting_date": posting_date},
		as_dict=True,
	)
	return {r.batch_no: r.qty for r in rows}


def _bundle_quantities(item_code, warehouse, posting_date):
	"""Quantities held in Serial and Batch Bundle entries.

	Returns an empty map where the bundle doctypes are absent, so this module
	keeps working on sites that never adopted them.
	"""
	if not frappe.db.table_exists("Serial and Batch Entry"):
		return {}

	rows = frappe.db.sql(
		"""
		select sbe.batch_no as batch_no, sum(sbe.qty) as qty
		from `tabSerial and Batch Entry` sbe
		inner join `tabSerial and Batch Bundle` sbb on sbb.name = sbe.parent
		where sbb.item_code = %(item_code)s
			and sbb.warehouse = %(warehouse)s
			and sbb.docstatus = 1
			and ifnull(sbb.is_cancelled, 0) = 0
			and ifnull(sbe.batch_no, '') != ''
			and sbb.posting_date <= %(posting_date)s
		group by sbe.batch_no
		""",
		{"item_code": item_code, "warehouse": warehouse, "posting_date": posting_date},
		as_dict=True,
	)
	return {r.batch_no: r.qty for r in rows}


def _candidate_batches(item_code, warehouse, posting_date, strategy, allow_expired):
	"""Batches with positive qty in `warehouse`, ordered by the chosen strategy."""
	available = batch_availability(item_code, warehouse, posting_date)
	if not available:
		return []

	batches = frappe.get_all(
		"Batch",
		filters={"name": ["in", list(available)], "item": item_code},
		fields=["name", "expiry_date", "creation", "disabled"],
	)

	rows = []
	for batch in batches:
		if batch.disabled:
			continue
		qty = flt(available.get(batch.name))
		if qty <= 0:
			continue
		if not allow_expired and batch.expiry_date and getdate(batch.expiry_date) < posting_date:
			continue
		rows.append(
			{
				"name": batch.name,
				"expiry_date": batch.expiry_date,
				"available": qty,
				"creation": batch.creation,
			}
		)

	if strategy == "FIFO by Creation":
		rows.sort(key=lambda r: r["creation"])
	else:
		rows.sort(key=lambda r: (getdate(r["expiry_date"] or FAR_FUTURE), r["creation"]))

	return rows


# ---------------------------------------------------------------------------
# messaging and diagnostics
# ---------------------------------------------------------------------------

def describe_shortage(item_code, warehouse, required, shortfall, posting_date=None):
	"""Explain a shortage in terms the user can act on.

	"short by 1" is useless when Stock Balance shows 500. Name the actual reason:
	no batch holds stock, everything expired, or genuinely not enough.
	"""
	base = _("{0}: need {1}, short by {2} in {3}").format(
		frappe.bold(item_code), flt(required, 6), flt(shortfall, 6), frappe.bold(warehouse)
	)

	if not is_batched(item_code):
		return base

	posting_date = getdate(posting_date or nowdate())
	available = batch_availability(item_code, warehouse, posting_date)
	total = sum(flt(q) for q in available.values() if flt(q) > 0)

	if total <= 0:
		return base + _(
			" &mdash; this item is batch tracked but no batch holds stock in that warehouse."
			" Receive it against a batch, or turn off Has Batch No on the item."
		)

	usable = _candidate_batches(item_code, warehouse, posting_date, "Nearest Expiry", False)
	if not usable:
		return base + _(
			" &mdash; {0} in stock but every batch is expired or disabled. Either receive fresh"
			" stock or tick Allow Expired Batches in Lab Consumption Settings."
		).format(flt(total, 6))

	return base + _(" &mdash; only {0} usable across {1} batch(es).").format(
		flt(sum(b["available"] for b in usable), 6), len(usable)
	)


@frappe.whitelist()
def explain(item_code, warehouse, posting_date=None):
	"""Show exactly what the allocator sees for one item.

	    bench --site <site> execute alphax_lab.lab.batch_selection.explain \\
	        --kwargs "{'item_code': 'STRIP-URINE', 'warehouse': 'Stores - A'}"
	"""
	posting_date = getdate(posting_date or nowdate())

	print(f"\n{item_code} in {warehouse} as of {posting_date}\n")
	print(f"  batch tracked        {'yes' if is_batched(item_code) else 'no'}")

	if not is_batched(item_code):
		print("  the allocator takes the full qty without any batch lookup.\n")
		return

	legacy = _legacy_quantities(item_code, warehouse, posting_date)
	bundle = _bundle_quantities(item_code, warehouse, posting_date)

	print(f"  legacy SLE batches   {len(legacy):>3}   total {flt(sum(legacy.values()), 6):g}")
	print(f"  bundle batches       {len(bundle):>3}   total {flt(sum(bundle.values()), 6):g}")

	usable = _candidate_batches(item_code, warehouse, posting_date, "Nearest Expiry", False)
	print(f"\n  usable, nearest expiry first: {len(usable)}\n")
	for batch in usable:
		print(f"    {batch['name']:32} qty {flt(batch['available']):>10g}   expires {batch['expiry_date'] or 'never'}")

	if not usable:
		blocked = _candidate_batches(item_code, warehouse, posting_date, "Nearest Expiry", True)
		if blocked:
			print("  none usable. Expired or disabled batches still holding stock:")
			for batch in blocked:
				print(f"    {batch['name']:32} qty {flt(batch['available']):>10g}   expired {batch['expiry_date']}")
		else:
			print("  no batch holds stock here, so the stock was received without a batch.")
	print()
