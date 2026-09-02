# Copyright (c) 2026, Neotec Integrated Solutions and contributors
# For license information, please see license.txt

"""Attributed vs unattributed lab store consumption.

Attributed   outflow booked by AlphaX Lab against a Sales Invoice / Delivery Note
Unattributed everything else leaving the lab store: QC runs, calibration,
             re-draws, breakage, expired write-offs, manual issues

A healthy lab shows a small, stable unattributed share. A growing one means the
per-document consumption model has drifted from what the bench actually uses.
"""

import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
	filters = frappe._dict(filters or {})
	_validate_filters(filters)

	attributed = _attributed(filters)
	total = _total_outflow(filters)

	data = []
	for item_code, outflow in total.items():
		booked = flt(attributed.get(item_code, 0))
		unattributed = flt(outflow) - booked
		share = (unattributed / outflow * 100) if outflow else 0

		data.append(
			{
				"item_code": item_code,
				"item_name": frappe.get_cached_value("Item", item_code, "item_name"),
				"stock_uom": frappe.get_cached_value("Item", item_code, "stock_uom"),
				"attributed_qty": booked,
				"unattributed_qty": unattributed,
				"total_qty": flt(outflow),
				"unattributed_pct": flt(share, 2),
			}
		)

	data.sort(key=lambda r: r["unattributed_qty"], reverse=True)
	return _columns(), data


def _validate_filters(filters):
	if not filters.get("warehouse"):
		settings = frappe.get_single("Lab Consumption Settings")
		filters.warehouse = settings.consumable_warehouse
	if not filters.get("warehouse"):
		frappe.throw(_("Select a warehouse, or set the Lab Store Warehouse in Lab Consumption Settings."))
	if not filters.get("from_date") or not filters.get("to_date"):
		frappe.throw(_("Select a date range."))


def _total_outflow(filters):
	rows = frappe.db.sql(
		"""
		select sle.item_code, sum(-sle.actual_qty) as qty
		from `tabStock Ledger Entry` sle
		where sle.warehouse = %(warehouse)s
			and sle.is_cancelled = 0
			and sle.actual_qty < 0
			and sle.posting_date between %(from_date)s and %(to_date)s
		group by sle.item_code
		""",
		filters,
		as_dict=True,
	)
	return {r.item_code: r.qty for r in rows}


def _attributed(filters):
	rows = frappe.db.sql(
		"""
		select sle.item_code, sum(-sle.actual_qty) as qty
		from `tabStock Ledger Entry` sle
		inner join `tabStock Entry` se
			on se.name = sle.voucher_no and sle.voucher_type = 'Stock Entry'
		where sle.warehouse = %(warehouse)s
			and sle.is_cancelled = 0
			and sle.actual_qty < 0
			and sle.posting_date between %(from_date)s and %(to_date)s
			and ifnull(se.source_document, '') != ''
		group by sle.item_code
		""",
		filters,
		as_dict=True,
	)
	return {r.item_code: r.qty for r in rows}


def _columns():
	return [
		{"fieldname": "item_code", "label": _("Item"), "fieldtype": "Link", "options": "Item", "width": 180},
		{"fieldname": "item_name", "label": _("Item Name"), "fieldtype": "Data", "width": 200},
		{"fieldname": "stock_uom", "label": _("UOM"), "fieldtype": "Link", "options": "UOM", "width": 80},
		{"fieldname": "attributed_qty", "label": _("Attributed"), "fieldtype": "Float", "width": 110},
		{"fieldname": "unattributed_qty", "label": _("Unattributed"), "fieldtype": "Float", "width": 120},
		{"fieldname": "total_qty", "label": _("Total Issued"), "fieldtype": "Float", "width": 110},
		{"fieldname": "unattributed_pct", "label": _("Unattributed %"), "fieldtype": "Percent", "width": 130},
	]
