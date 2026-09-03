# Copyright (c) 2026, Neotec Integrated Solutions and contributors
# For license information, please see license.txt

"""Demo data for testing the consumption flow end to end.

    bench --site <site> execute alphax_lab.demo.demo_data.setup
    bench --site <site> execute alphax_lab.demo.demo_data.run_test
    bench --site <site> execute alphax_lab.demo.demo_data.teardown

`setup` is idempotent: run it as many times as you like. It creates a lab store,
consumable items (three of them batched with different expiry dates so nearest
expiry selection is actually exercised), three test items with their consumable
lists, the Plasma Test Map rows, and receives opening stock.

`run_test` posts a two-test Delivery Note and prints the resulting Stock Entry so
you can see exactly what was consumed and from which batch.

Everything created here is prefixed DEMO- so `teardown` can find it again.
"""

import frappe
from frappe.utils import add_days, flt, nowdate

PREFIX = "DEMO-"

CONSUMABLES = [
	# code,           name,                  uom,   batched
	("NEEDLE-21G", "Needle 21G", "Nos", False),
	("COTTON-BALL", "Cotton Ball", "Nos", False),
	("ALCOHOL-SWAB", "Alcohol Swab", "Nos", False),
	("GLOVES-NITRILE", "Nitrile Gloves (pair)", "Nos", False),
	("TUBE-EDTA", "EDTA Tube 3ml", "Nos", False),
	("TUBE-SERUM", "Serum Tube 5ml", "Nos", False),
	("CUP-URINE", "Urine Cup 60ml", "Nos", False),
	("DIPSTICK-URINE", "Urine Dipstick", "Nos", False),
	("CUVETTE", "Reaction Cuvette", "Nos", False),
	("REAGENT-CBC", "CBC Reagent Pack", "Nos", True),
	("REAGENT-LFT", "LFT Reagent Set", "Nos", True),
	("CONTROL-CBC", "CBC Control Serum", "Nos", True),
]

# Two batches per batched item, deliberately different expiry dates.
BATCHES = {
	"REAGENT-CBC": [("B-CBC-EARLY", 45, 20), ("B-CBC-LATE", 400, 30)],
	"REAGENT-LFT": [("B-LFT-EARLY", 60, 15), ("B-LFT-LATE", 380, 25)],
	"CONTROL-CBC": [("B-CTRL-EARLY", 30, 10), ("B-CTRL-LATE", 300, 20)],
}

OPENING_QTY = 200

TESTS = [
	{
		"code": "LAB-CBC",
		"name": "Complete Blood Count",
		"rate": 45,
		"sample_type": "Whole Blood EDTA",
		"consumables": [
			("NEEDLE-21G", 1),
			("COTTON-BALL", 2),
			("ALCOHOL-SWAB", 1),
			("GLOVES-NITRILE", 1),
			("TUBE-EDTA", 1),
			("REAGENT-CBC", 1),
			("CONTROL-CBC", 0.05),
		],
	},
	{
		"code": "LAB-LFT",
		"name": "Liver Function Test",
		"rate": 90,
		"sample_type": "Serum",
		"consumables": [
			("NEEDLE-21G", 1),
			("COTTON-BALL", 2),
			("ALCOHOL-SWAB", 1),
			("GLOVES-NITRILE", 1),
			("TUBE-SERUM", 1),
			("REAGENT-LFT", 1),
			("CUVETTE", 4),
		],
	},
	{
		"code": "LAB-URINE",
		"name": "Urine Routine",
		"rate": 30,
		"sample_type": "Urine",
		"consumables": [
			("CUP-URINE", 1),
			("DIPSTICK-URINE", 1),
		],
	},
]


# ---------------------------------------------------------------------------
# setup
# ---------------------------------------------------------------------------

def setup():
	company = _company()
	abbr = frappe.get_cached_value("Company", company, "abbr")
	warehouse = _warehouse(company, abbr)

	_item_group("Lab Tests")
	_item_group("Lab Consumables")

	for code, name, uom, batched in CONSUMABLES:
		_consumable_item(code, name, uom, batched)

	for test in TESTS:
		_test_item(test)

	_receive_opening_stock(company, warehouse)
	_configure_settings(company, warehouse)

	frappe.db.commit()

	print("\nDemo data ready.")
	print(f"  Warehouse    {warehouse}")
	print(f"  Tests        {', '.join(PREFIX + t['code'] for t in TESTS)}")
	print(f"  Consumables  {len(CONSUMABLES)} items, {len(BATCHES)} batched")
	print("\nNext: bench --site <site> execute alphax_lab.demo.demo_data.run_test")


def _company():
	company = frappe.defaults.get_defaults().get("company")
	if not company:
		company = frappe.get_all("Company", pluck="name", limit=1)
		company = company[0] if company else None
	if not company:
		frappe.throw("No Company found. Create one first.")
	return company


def _warehouse(company, abbr):
	name = f"Lab Store - {abbr}"
	if frappe.db.exists("Warehouse", name):
		return name

	parent = f"All Warehouses - {abbr}"
	doc = frappe.new_doc("Warehouse")
	doc.warehouse_name = "Lab Store"
	doc.company = company
	if frappe.db.exists("Warehouse", parent):
		doc.parent_warehouse = parent
	doc.flags.ignore_permissions = True
	doc.insert()
	return doc.name


def _item_group(name):
	if frappe.db.exists("Item Group", name):
		return name
	doc = frappe.new_doc("Item Group")
	doc.item_group_name = name
	doc.parent_item_group = "All Item Groups"
	doc.is_group = 0
	doc.flags.ignore_permissions = True
	doc.insert()
	return doc.name


def _consumable_item(code, name, uom, batched):
	item_code = PREFIX + code
	if frappe.db.exists("Item", item_code):
		return item_code

	doc = frappe.new_doc("Item")
	doc.item_code = item_code
	doc.item_name = name
	doc.item_group = "Lab Consumables"
	doc.stock_uom = uom
	doc.is_stock_item = 1
	doc.is_sales_item = 0
	doc.is_purchase_item = 1
	if batched:
		doc.has_batch_no = 1
		doc.has_expiry_date = 1
		doc.create_new_batch = 1
		doc.batch_number_series = f"{item_code}-.####"
	doc.flags.ignore_permissions = True
	doc.insert()
	return doc.name


def _test_item(test):
	item_code = PREFIX + test["code"]

	if frappe.db.exists("Item", item_code):
		doc = frappe.get_doc("Item", item_code)
	else:
		doc = frappe.new_doc("Item")
		doc.item_code = item_code
		doc.item_name = test["name"]
		doc.item_group = "Lab Tests"
		doc.stock_uom = "Nos"
		doc.is_stock_item = 0
		doc.is_sales_item = 1

	doc.flags.ignore_permissions = True
	doc.save()

	_consumption_record(test, item_code)
	_test_map(test, item_code)
	return item_code


def _consumption_record(test, item_code):
	existing = frappe.db.get_value("Lab Test Consumption", {"item": item_code})
	doc = frappe.get_doc("Lab Test Consumption", existing) if existing else frappe.new_doc(
		"Lab Test Consumption"
	)
	doc.item = item_code
	doc.is_active = 1
	doc.set("consumables", [])
	for code, qty in test["consumables"]:
		doc.append("consumables", {"item": PREFIX + code, "qty": qty})
	doc.flags.ignore_permissions = True
	doc.save()
	return doc.name


def _test_map(test, item_code):
	map_name = PREFIX + test["name"]
	if frappe.db.exists("Plasma Test Map", map_name):
		return map_name

	doc = frappe.new_doc("Plasma Test Map")
	doc.plasma_test_name = map_name
	doc.plasma_test_code = test["code"]
	doc.item = item_code
	if frappe.db.exists("Lab Sample Type", test["sample_type"]):
		doc.sample_type = test["sample_type"]
	doc.is_active = 1
	doc.flags.ignore_permissions = True
	doc.insert()
	return doc.name


def _receive_opening_stock(company, warehouse):
	if frappe.db.exists("Stock Entry", {"remarks": ["like", "%AlphaX Lab demo opening stock%"], "docstatus": 1}):
		print("Opening stock already received, skipping.")
		return

	entry = frappe.new_doc("Stock Entry")
	entry.company = company
	entry.purpose = "Material Receipt"
	entry.stock_entry_type = "Material Receipt"
	entry.remarks = "AlphaX Lab demo opening stock"

	for code, _name, _uom, batched in CONSUMABLES:
		item_code = PREFIX + code

		if not batched:
			row = entry.append("items", {})
			row.item_code = item_code
			row.qty = OPENING_QTY
			row.t_warehouse = warehouse
			row.basic_rate = 1
			continue

		for batch_id, expiry_offset, qty in BATCHES[code]:
			batch_name = _batch(item_code, PREFIX + batch_id, expiry_offset)
			row = entry.append("items", {})
			row.item_code = item_code
			row.qty = qty
			row.t_warehouse = warehouse
			row.basic_rate = 25
			row.use_serial_batch_fields = 1
			row.batch_no = batch_name

	entry.flags.ignore_permissions = True
	entry.insert()
	entry.submit()
	print(f"Opening stock received: {entry.name}")


def _batch(item_code, batch_id, expiry_offset):
	if frappe.db.exists("Batch", batch_id):
		return batch_id

	doc = frappe.new_doc("Batch")
	doc.batch_id = batch_id
	doc.item = item_code
	doc.expiry_date = add_days(nowdate(), expiry_offset)
	doc.flags.ignore_permissions = True
	doc.insert()
	return doc.name


def _configure_settings(company, warehouse):
	settings = frappe.get_single("Lab Consumption Settings")
	settings.enabled = 1
	settings.company = company
	settings.consumable_warehouse = warehouse
	settings.consume_on_delivery_note = 1
	settings.consume_on_sales_invoice = 0
	settings.batch_strategy = "Nearest Expiry"
	settings.block_on_shortage = 1
	settings.unconfigured_item_action = "Block on Submit"

	existing = {d.item_group for d in settings.get("lab_item_groups", [])}
	if "Lab Tests" not in existing:
		settings.append("lab_item_groups", {"item_group": "Lab Tests"})

	settings.flags.ignore_permissions = True
	settings.flags.ignore_mandatory = True
	settings.save()


# ---------------------------------------------------------------------------
# end-to-end test
# ---------------------------------------------------------------------------

def run_test():
	"""Post a two-test Delivery Note and show what it consumed."""
	company = _company()
	customer = _customer()

	note = frappe.new_doc("Delivery Note")
	note.company = company
	note.customer = customer
	note.plasma_ref = f"DEMO-PLS-{frappe.generate_hash(length=6).upper()}"

	for code, qty, rate in [("LAB-CBC", 1, 45), ("LAB-LFT", 1, 90)]:
		row = note.append("items", {})
		row.item_code = PREFIX + code
		row.qty = qty
		row.rate = rate

	note.flags.ignore_permissions = True
	note.insert()
	note.submit()

	print(f"\nDelivery Note {note.name} submitted ({note.plasma_ref})")
	print("  Billed lines:")
	for row in note.items:
		print(f"    {row.item_code:24} qty {flt(row.qty):g}  rate {flt(row.rate):g}")

	entry_name = frappe.db.get_value(
		"Stock Entry",
		{"source_doctype": "Delivery Note", "source_document": note.name, "docstatus": 1},
		"name",
	)
	if not entry_name:
		print("\n  No Stock Entry created. Check Lab Consumption Settings is enabled.")
		return

	entry = frappe.get_doc("Stock Entry", entry_name)
	print(f"\n  Consumption Stock Entry {entry.name}:")
	for row in entry.items:
		batch = f"  batch {row.batch_no}" if row.batch_no else ""
		print(f"    {row.item_code:24} qty {flt(row.qty):g}{batch}")

	print("\n  Expect two needles and two cotton pairs: each test carries its own draw items.")
	print("  Expect the earlier-expiry batch to be picked for the reagents.")
	print(f"\n  Cancel to reverse: frappe.get_doc('Delivery Note', '{note.name}').cancel()")


def _customer():
	name = PREFIX + "Walk-in Patient"
	if frappe.db.exists("Customer", name):
		return name
	doc = frappe.new_doc("Customer")
	doc.customer_name = name
	doc.customer_group = frappe.get_all("Customer Group", {"is_group": 0}, pluck="name", limit=1)[0]
	doc.territory = frappe.get_all("Territory", {"is_group": 0}, pluck="name", limit=1)[0]
	doc.flags.ignore_permissions = True
	doc.insert()
	return doc.name


# ---------------------------------------------------------------------------
# teardown
# ---------------------------------------------------------------------------

def teardown():
	"""Cancel and delete everything prefixed DEMO-.

	Submitted stock documents must be cancelled before their items can go, so
	this runs in dependency order. Anything that will not delete is reported
	rather than forced.
	"""
	stuck = []

	for doctype in ("Delivery Note", "Sales Invoice"):
		for name in frappe.get_all(doctype, {"plasma_ref": ["like", f"{PREFIX}%"]}, pluck="name"):
			_cancel_and_delete(doctype, name, stuck)

	for name in frappe.get_all(
		"Stock Entry", {"remarks": ["like", "%AlphaX Lab demo%"]}, pluck="name"
	):
		_cancel_and_delete("Stock Entry", name, stuck)

	for name in frappe.get_all("Lab Test Consumption", {"item": ["like", f"{PREFIX}%"]}, pluck="name"):
		try:
			frappe.delete_doc("Lab Test Consumption", name, ignore_permissions=True)
		except Exception as exc:
			stuck.append(f"Lab Test Consumption {name}: {exc}")

	for doctype in ("Plasma Test Map", "Batch", "Item", "Customer"):
		field = "name"
		for name in frappe.get_all(doctype, {field: ["like", f"{PREFIX}%"]}, pluck="name"):
			try:
				frappe.delete_doc(doctype, name, force=False, ignore_permissions=True)
			except Exception as exc:
				stuck.append(f"{doctype} {name}: {exc}")

	frappe.db.commit()

	if stuck:
		print("\nCould not remove:")
		for line in stuck:
			print(f"  {line}")
	else:
		print("\nDemo data removed.")


def _cancel_and_delete(doctype, name, stuck):
	try:
		doc = frappe.get_doc(doctype, name)
		if doc.docstatus == 1:
			doc.flags.ignore_permissions = True
			doc.cancel()
		frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)
	except Exception as exc:
		stuck.append(f"{doctype} {name}: {exc}")
