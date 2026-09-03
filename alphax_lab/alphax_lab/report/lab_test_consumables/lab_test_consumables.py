# Copyright (c) 2026, Neotec Integrated Solutions and contributors
# For license information, please see license.txt

"""Every test and what it consumes, flattened into one view.

Consumables are defined per test on the Item form, which is correct but hard to
review: you cannot compare ten tests without opening ten items. This report is
the reviewable version. Use it to spot a test that lists two needles by mistake,
or a reagent that never got added.

Stock on hand is shown alongside each consumable so a supervisor can see which
definitions are about to fail at the counter.
"""

import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
	filters = frappe._dict(filters or {})
	settings = frappe.get_single("Lab Consumption Settings")
	warehouse = filters.get("warehouse") or settings.consumable_warehouse

	tests = _tests(filters)
	if not tests:
		return _columns(), []

	rows = frappe.get_all(
		"Lab Consumable Item",
		filters={"parent": ["in", [t.name for t in tests]], "parenttype": "Item"},
		fields=["parent", "item", "qty", "idx"],
		order_by="parent asc, idx asc",
	)

	by_test = {}
	for row in rows:
		by_test.setdefault(row.parent, []).append(row)

	stock = _stock_map({r.item for r in rows}, warehouse) if warehouse else {}

	data = []
	for test in tests:
		consumables = by_test.get(test.name, [])

		if not consumables:
			data.append(
				{
					"test_item": test.name,
					"test_name": test.item_name,
					"consumable": None,
					"qty": None,
					"uom": None,
					"batched": 0,
					"stock_on_hand": None,
					"indent": 0,
					"note": _("No consumables defined"),
				}
			)
			continue

		data.append(
			{
				"test_item": test.name,
				"test_name": test.item_name,
				"indent": 0,
				"note": _("{0} consumable(s)").format(len(consumables)),
			}
		)

		for row in consumables:
			item = frappe.get_cached_doc("Item", row.item)
			data.append(
				{
					"test_item": None,
					"test_name": None,
					"consumable": row.item,
					"consumable_name": item.item_name,
					"qty": flt(row.qty),
					"uom": item.stock_uom,
					"batched": item.has_batch_no,
					"stock_on_hand": stock.get(row.item),
					"indent": 1,
				}
			)

	return _columns(), data


def _tests(filters):
	settings = frappe.get_single("Lab Consumption Settings")
	lab_groups = [d.item_group for d in settings.get("lab_item_groups", []) if d.item_group]

	item_filters = {"disabled": 0}
	if filters.get("test_item"):
		item_filters["name"] = filters.get("test_item")
	elif lab_groups:
		item_filters["item_group"] = ["in", lab_groups]
	else:
		mapped = frappe.get_all("Plasma Test Map", {"is_active": 1}, pluck="item")
		if not mapped:
			return []
		item_filters["name"] = ["in", mapped]

	return frappe.get_all(
		"Item", filters=item_filters, fields=["name", "item_name"], order_by="name asc"
	)


def _stock_map(item_codes, warehouse):
	if not item_codes:
		return {}
	rows = frappe.get_all(
		"Bin",
		filters={"item_code": ["in", list(item_codes)], "warehouse": warehouse},
		fields=["item_code", "actual_qty"],
	)
	return {r.item_code: flt(r.actual_qty) for r in rows}


def _columns():
	return [
		{"fieldname": "test_item", "label": _("Test"), "fieldtype": "Link", "options": "Item", "width": 160},
		{"fieldname": "test_name", "label": _("Test Name"), "fieldtype": "Data", "width": 180},
		{"fieldname": "consumable", "label": _("Consumable"), "fieldtype": "Link", "options": "Item", "width": 160},
		{"fieldname": "consumable_name", "label": _("Consumable Name"), "fieldtype": "Data", "width": 180},
		{"fieldname": "qty", "label": _("Qty per Test"), "fieldtype": "Float", "width": 110},
		{"fieldname": "uom", "label": _("UOM"), "fieldtype": "Link", "options": "UOM", "width": 80},
		{"fieldname": "batched", "label": _("Batched"), "fieldtype": "Check", "width": 80},
		{"fieldname": "stock_on_hand", "label": _("Stock on Hand"), "fieldtype": "Float", "width": 120},
		{"fieldname": "note", "label": _("Note"), "fieldtype": "Data", "width": 180},
	]
