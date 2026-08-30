# Copyright (c) 2026, Neotec Integrated Solutions and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class LabSampleType(Document):
	def validate(self):
		self.validate_container_item()

	def validate_container_item(self):
		if not self.container_item:
			return

		consumables = frappe.get_all(
			"Lab Consumable Item",
			filters={"parent": self.container_item, "parenttype": "Item"},
			limit=1,
		)
		if not consumables:
			frappe.msgprint(
				_("Container item {0} has no Lab Consumables defined. No container stock will be issued for this sample type.").format(
					frappe.bold(self.container_item)
				),
				indicator="orange",
				alert=True,
			)
