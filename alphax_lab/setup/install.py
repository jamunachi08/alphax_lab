# Copyright (c) 2026, Neotec Integrated Solutions and contributors
# For license information, please see license.txt

"""Idempotent setup. Safe to run on every install and every migrate."""

import json

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


def setup():
	create_custom_fields(CUSTOM_FIELDS, ignore_validate=True)
	seed_sample_types()
	seed_settings()
	seed_workspace()
	frappe.db.commit()


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
