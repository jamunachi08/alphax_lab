# Copyright (c) 2026, Neotec Integrated Solutions and contributors
# For license information, please see license.txt

"""Idempotent setup. Safe to run on every install and every migrate."""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

CUSTOM_FIELDS = {
	"Item": [
		{
			"fieldname": "lab_consumables_section",
			"label": "Lab Consumables",
			"fieldtype": "Section Break",
			"insert_after": "item_group",
			"collapsible": 1,
			"module": "Alphax Lab",
		},
		{
			"fieldname": "lab_consumables",
			"label": "Lab Consumables",
			"fieldtype": "Table",
			"options": "Lab Consumable Item",
			"insert_after": "lab_consumables_section",
			"description": (
				"Stock consumed each time one unit of this item is sold. Define the full "
				"consumable list for each lab test here."
			),
			"module": "Alphax Lab",
		},
	],
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
