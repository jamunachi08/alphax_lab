# Copyright (c) 2026, Neotec Integrated Solutions and contributors
# For license information, please see license.txt

"""Idempotent setup. Safe to run on every install and every migrate."""

import json
import time

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

CUSTOM_FIELDS = {
	"Sales Invoice": [
		{
			"fieldname": "plasma_ref",
			"label": "Plasma Reference",
			"fieldtype": "Data",
			"insert_after": "po_no",
			"unique": 1,
			"no_copy": 1,
			"search_index": 1,
			"module": "Alphax Lab",
		}
	],
	"Delivery Note": [
		{
			"fieldname": "plasma_ref",
			"label": "Plasma Reference",
			"fieldtype": "Data",
			"insert_after": "po_no",
			"unique": 1,
			"no_copy": 1,
			"search_index": 1,
			"module": "Alphax Lab",
		}
	],
	"Stock Entry": [
		{
			"fieldname": "lab_source_section",
			"label": "Lab Consumption Source",
			"fieldtype": "Section Break",
			"insert_after": "remarks",
			"collapsible": 1,
			"module": "Alphax Lab",
		},
		{
			"fieldname": "source_doctype",
			"label": "Source Document Type",
			"fieldtype": "Link",
			"options": "DocType",
			"insert_after": "lab_source_section",
			"read_only": 1,
			"no_copy": 1,
			"module": "Alphax Lab",
		},
		{
			"fieldname": "source_document",
			"label": "Source Document",
			"fieldtype": "Dynamic Link",
			"options": "source_doctype",
			"insert_after": "source_doctype",
			"read_only": 1,
			"no_copy": 1,
			"search_index": 1,
			"module": "Alphax Lab",
		},
		{
			"fieldname": "plasma_ref",
			"label": "Plasma Reference",
			"fieldtype": "Data",
			"insert_after": "source_document",
			"read_only": 1,
			"no_copy": 1,
			"module": "Alphax Lab",
		},
	],
}

DEFAULT_SAMPLE_TYPES = [
	{"sample_type_name": "Whole Blood EDTA", "sample_type_name_ar": "دم كامل EDTA"},
	{"sample_type_name": "Serum", "sample_type_name_ar": "مصل"},
	{"sample_type_name": "Plasma Citrate", "sample_type_name_ar": "بلازما سيترات"},
	{"sample_type_name": "Urine", "sample_type_name_ar": "بول"},
	{"sample_type_name": "Stool", "sample_type_name_ar": "براز"},
	{"sample_type_name": "Swab", "sample_type_name_ar": "مسحة"},
]


def after_install():
	setup()


def after_migrate():
	setup()


DEADLOCK_RETRIES = 4
DEADLOCK_BACKOFF = 2  # seconds, doubled each attempt


def setup():
	"""Idempotent setup, tolerant of lock contention.

	Adding `plasma_ref` with unique=1 runs an ALTER TABLE on Sales Invoice,
	Delivery Note and Stock Entry. On a site with existing data and a live
	scheduler, that can deadlock against ordinary writes. Each step is retried
	with backoff and committed separately, so a loser in one race does not undo
	the steps that already succeeded.
	"""
	steps = [
		("custom fields", lambda: create_custom_fields(CUSTOM_FIELDS, ignore_validate=True)),
		("sample types", seed_sample_types),
		("settings", seed_settings),
		("workspace", seed_workspace),
	]

	failed = []
	for label, fn in steps:
		try:
			_with_retry(label, fn)
			frappe.db.commit()
		except Exception:
			frappe.db.rollback()
			failed.append(label)
			frappe.log_error(
				title=f"AlphaX Lab setup step failed: {label}",
				message=frappe.get_traceback(),
			)

	if failed:
		print(
			"AlphaX Lab: these setup steps did not complete: "
			+ ", ".join(failed)
			+ ". Re-run `bench --site <site> migrate`, ideally with the scheduler paused."
		)


def _with_retry(label, fn):
	"""Retry a step on deadlock or lock-wait timeout, then give up."""
	delay = DEADLOCK_BACKOFF

	for attempt in range(1, DEADLOCK_RETRIES + 1):
		try:
			fn()
			return
		except Exception as exc:
			if not _is_lock_error(exc) or attempt == DEADLOCK_RETRIES:
				raise
			frappe.db.rollback()
			print(f"AlphaX Lab: lock contention on {label}, retry {attempt} of {DEADLOCK_RETRIES - 1} in {delay}s")
			time.sleep(delay)
			delay *= 2


def _is_lock_error(exc):
	text = str(exc).lower()
	return "deadlock" in text or "lock wait timeout" in text or "try restarting transaction" in text


def seed_sample_types():
	for row in DEFAULT_SAMPLE_TYPES:
		if frappe.db.exists("Lab Sample Type", row["sample_type_name"]):
			continue
		doc = frappe.new_doc("Lab Sample Type")
		doc.update(row)
		doc.is_active = 1
		doc.flags.ignore_permissions = True
		doc.insert()


def seed_workspace():
	"""A visible home for the app.

	Without this, Lab Test Consumption is reachable only by typing its name into
	the awesomebar, which nobody does for a doctype they do not yet know exists.
	Failure here is logged, never raised: a broken workspace must not block a
	migrate.
	"""
	try:
		if frappe.db.exists("Workspace", "Lab"):
			return

		doc = frappe.new_doc("Workspace")
		doc.name = "Lab"
		doc.title = "Lab"
		doc.label = "Lab"
		doc.module = "Alphax Lab"
		doc.icon = "health"
		doc.public = 1

		shortcuts = [
			("Lab Test Consumption", "DocType"),
			("Plasma Test Map", "DocType"),
			("Lab Consumption Settings", "DocType"),
			("Lab Test Consumables", "Report"),
			("Unconfigured Lab Items", "Report"),
			("Lab Consumption Variance", "Report"),
		]

		content = [
			{
				"id": "lab_header",
				"type": "header",
				"data": {"text": "<span class='h4'>Lab Consumption</span>", "col": 12},
			}
		]
		for label, link_type in shortcuts:
			doc.append(
				"shortcuts",
				{"label": label, "link_to": label, "type": link_type},
			)
			content.append(
				{"id": label.replace(" ", "_").lower(), "type": "shortcut", "data": {"shortcut_name": label, "col": 4}}
			)

		doc.content = json.dumps(content)
		doc.flags.ignore_permissions = True
		doc.insert()
	except Exception:
		frappe.log_error(title="AlphaX Lab workspace setup failed", message=frappe.get_traceback())


def seed_settings():
	settings = frappe.get_single("Lab Consumption Settings")

	if not settings.get("lab_item_groups"):
		if frappe.db.exists("Item Group", "Lab Tests"):
			settings.append("lab_item_groups", {"item_group": "Lab Tests"})

	if not settings.stock_entry_type and frappe.db.exists("Stock Entry Type", "Material Issue"):
		settings.stock_entry_type = "Material Issue"

	if not settings.batch_strategy:
		settings.batch_strategy = "Nearest Expiry"

	settings.flags.ignore_permissions = True
	settings.flags.ignore_mandatory = True
	settings.save()


def status():
	"""Report what setup actually created.

	    bench --site <site> execute alphax_lab.setup.install.status

	Run this after an install that errored, to see what landed before the
	failure and what still needs a re-run.
	"""
	print("\nAlphaX Lab setup status\n")

	for doctype in (
		"Lab Test Consumption",
		"Plasma Test Map",
		"Lab Sample Type",
		"Lab Consumption Settings",
		"Lab Consumable Item",
		"Lab Item Group Filter",
	):
		mark = "yes" if frappe.db.exists("DocType", doctype) else "MISSING"
		print(f"  doctype   {doctype:28} {mark}")

	print()
	for dt, fields in CUSTOM_FIELDS.items():
		for field in fields:
			exists = frappe.db.exists("Custom Field", {"dt": dt, "fieldname": field["fieldname"]})
			mark = "yes" if exists else "MISSING"
			print(f"  field     {dt} . {field['fieldname']:24} {mark}")

	print()
	print(f"  workspace Lab{' ' * 29}{'yes' if frappe.db.exists('Workspace', 'Lab') else 'MISSING'}")

	settings = frappe.get_single("Lab Consumption Settings")
	print(f"  settings  enabled{' ' * 25}{'yes' if settings.enabled else 'no'}")
	print(f"  settings  warehouse{' ' * 23}{settings.consumable_warehouse or 'NOT SET'}")
	print(f"  sample types{' ' * 26}{frappe.db.count('Lab Sample Type')}")
	print(f"  test consumption records{' ' * 14}{frappe.db.count('Lab Test Consumption')}")
	print()
