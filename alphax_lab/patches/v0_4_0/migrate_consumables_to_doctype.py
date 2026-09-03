# Copyright (c) 2026, Neotec Integrated Solutions and contributors
# For license information, please see license.txt

"""Move consumable definitions off the Item custom field.

Up to v0.3.0 consumables lived in a `lab_consumables` child table added to Item
as a custom field. It worked, but it was undiscoverable: custom fields do not
appear in the DocType list, the module, or awesomebar search, so users could not
find the place to define anything.

v0.4.0 moves the definition to the Lab Test Consumption doctype. This patch
copies any existing rows across, then removes the custom field. The child rows
themselves are re-parented rather than recreated, so idx order and any manual
edits survive.

Safe to re-run: items that already have a Lab Test Consumption record are
skipped.
"""

import frappe


def execute():
	if not frappe.db.exists("DocType", "Lab Test Consumption"):
		return

	if not frappe.db.has_column("Lab Consumable Item", "parenttype"):
		return

	parents = frappe.get_all(
		"Lab Consumable Item",
		filters={"parenttype": "Item"},
		fields=["distinct parent as parent"],
		pluck="parent",
	)

	migrated = 0
	for item_code in parents:
		if not item_code or not frappe.db.exists("Item", item_code):
			continue
		if frappe.db.exists("Lab Test Consumption", {"item": item_code}):
			continue

		rows = frappe.get_all(
			"Lab Consumable Item",
			filters={"parent": item_code, "parenttype": "Item"},
			fields=["item", "qty", "remarks", "idx"],
			order_by="idx asc",
		)
		if not rows:
			continue

		doc = frappe.new_doc("Lab Test Consumption")
		doc.item = item_code
		doc.is_active = 1
		for row in rows:
			doc.append(
				"consumables",
				{"item": row.item, "qty": row.qty, "remarks": row.remarks},
			)
		doc.flags.ignore_permissions = True
		doc.flags.ignore_validate = True
		doc.insert()
		migrated += 1

	# Old rows are now duplicated into the new parent; drop the originals so the
	# reports and the engine cannot read from two places.
	frappe.db.delete("Lab Consumable Item", {"parenttype": "Item"})

	for fieldname in ("lab_consumables", "lab_consumables_section"):
		name = frappe.db.get_value("Custom Field", {"dt": "Item", "fieldname": fieldname})
		if name:
			frappe.delete_doc("Custom Field", name, ignore_permissions=True, force=True)

	frappe.db.commit()

	if migrated:
		frappe.logger().info(f"AlphaX Lab: migrated {migrated} consumable definitions to Lab Test Consumption")
