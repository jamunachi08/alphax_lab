# Copyright (c) 2026, Neotec Integrated Solutions and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class PlasmaTestMap(Document):
	def validate(self):
		self.validate_item_is_not_bundled()

	def validate_item_is_not_bundled(self):
		"""A Product Bundle on the test item would consume stock through Packed
		Items as well as through this app's Stock Entry, double counting."""
		if frappe.db.exists("Product Bundle", {"new_item_code": self.item, "disabled": 0}):
			frappe.throw(
				_("Item {0} has an active Product Bundle. Disable it before mapping the item here, otherwise consumption is booked twice.").format(
					frappe.bold(self.item)
				),
				title=_("Double Consumption Risk"),
			)
