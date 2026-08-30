# Copyright (c) 2026, Neotec Integrated Solutions and contributors
# For license information, please see license.txt

"""Batch allocation for lab consumable issues.

ERPNext v15 routes batch tracking through the Serial and Batch Bundle. Creating
those bundles from code for every consumable line is slow and fragile, so this
module sets `use_serial_batch_fields = 1` on the Stock Entry Detail row and
populates the legacy `batch_no` field. ERPNext builds the bundle on submit.

The allocator returns one row per (batch, qty) pair, so a single consumable
requirement may expand into several Stock Entry Detail rows when no single
batch can cover it.
"""

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate

FAR_FUTURE = "2999-12-31"


def allocate(item_code, warehouse, qty, posting_date=None, strategy="Nearest Expiry", allow_expired=False):
	"""Split `qty` of `item_code` across available batches.

	Returns a list of dicts: [{"qty": float, "batch_no": str | None}, ...]
	plus a shortfall float. Non-batched items return a single row with
	batch_no None and no batch lookup at all.
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


def _candidate_batches(item_code, warehouse, posting_date, strategy, allow_expired):
	"""Batches with positive qty in `warehouse`, ordered by the chosen strategy."""
	if strategy == "FIFO by Creation":
		order_by = "batch.creation asc"
	else:
		order_by = f"ifnull(batch.expiry_date, '{FAR_FUTURE}') asc, batch.creation asc"

	rows = frappe.db.sql(
		f"""
		select
			batch.name,
			batch.expiry_date,
			sum(sle.actual_qty) as available
		from `tabBatch` batch
		inner join `tabStock Ledger Entry` sle
			on sle.batch_no = batch.name
		where
			batch.item = %(item_code)s
			and ifnull(batch.disabled, 0) = 0
			and sle.warehouse = %(warehouse)s
			and sle.is_cancelled = 0
			and sle.posting_date <= %(posting_date)s
		group by batch.name, batch.expiry_date, batch.creation
		having sum(sle.actual_qty) > 0
		order by {order_by}
		""",
		{"item_code": item_code, "warehouse": warehouse, "posting_date": posting_date},
		as_dict=True,
	)

	if allow_expired:
		return rows

	return [r for r in rows if not r.expiry_date or getdate(r.expiry_date) >= posting_date]


def describe_shortage(item_code, warehouse, required, shortfall):
	return _("{0}: need {1}, short by {2} in {3}").format(
		frappe.bold(item_code), flt(required, 6), flt(shortfall, 6), frappe.bold(warehouse)
	)
