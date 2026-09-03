# Copyright (c) 2026, Neotec Integrated Solutions and contributors
# For license information, please see license.txt

"""Every item that would consume no stock if sold.

Run this after setup and after any bulk item import. Finding these here is
cheap; finding them one at a time as users hit a blocked document is not.

Two failure modes are reported:

    no active Plasma Test Map     the item was never mapped, or the map is inactive
    Lab Consumables table empty   mapped, but nothing is defined to consume

The second is the one that hides. The item looks configured from the list view
and only reveals itself when you open the consumables tab.
"""

import frappe
from frappe import _
from frappe.utils import cint


def execute(filters=None):
	filters = frappe._dict(filters or {})
	settings = frappe.get_single("Lab Consumption Settings")

	lab_groups = [d.item_group for d in settings.get("lab_item_groups", []) if d.item_group]
	if not lab_groups:
		frappe.msgprint(
			_("No Lab Item Groups configured in Lab Consumption Settings, so nothing is in scope."),
			indicator="orange",
		)
		return _columns(), []

	item_filters = {"item_group": ["in", lab_groups]}
	if not cint(filters.get("include_disabled")):
		item_filters["disabled"] = 0

	items = frappe.get_all(
		"Item",
		filters=item_filters,
		fields=["name", "item_name", "item_group", "disabled"],
		order_by="item_group asc, name asc",
	)
	if not items:
		return _columns(), []

	item_codes = [i.name for i in items]

	mapped = set(
		frappe.get_all(
			"Plasma Test Map",
			filters={"item": ["in", item_codes], "is_active": 1},
			pluck="item",
		)
	)

	with_consumables = set(
		frappe.get_all(
			"Lab Consumable Item",
			filters={"parent": ["in", item_codes], "parenttype": "Item"},
			pluck="parent",
		)
	)

	data = []
	for item in items:
		if item.name not in mapped:
			issue = _("No active Plasma Test Map")
			fix = _("Add a Plasma Test Map row, or move the item out of the lab item groups")
		elif item.name not in with_consumables:
			issue = _("Lab Consumables table is empty")
			fix = _("Fill the Lab Consumables table on the item")
		else:
			continue

		data.append(
			{
				"item_code": item.name,
				"item_name": item.item_name,
				"item_group": item.item_group,
				"disabled": item.disabled,
				"issue": issue,
				"suggested_fix": fix,
			}
		)

	return _columns(), data


def _columns():
	return [
		{"fieldname": "item_code", "label": _("Item"), "fieldtype": "Link", "options": "Item", "width": 180},
		{"fieldname": "item_name", "label": _("Item Name"), "fieldtype": "Data", "width": 200},
		{"fieldname": "item_group", "label": _("Item Group"), "fieldtype": "Link", "options": "Item Group", "width": 150},
		{"fieldname": "disabled", "label": _("Disabled"), "fieldtype": "Check", "width": 80},
		{"fieldname": "issue", "label": _("Issue"), "fieldtype": "Data", "width": 220},
		{"fieldname": "suggested_fix", "label": _("Suggested Fix"), "fieldtype": "Data", "width": 380},
	]
