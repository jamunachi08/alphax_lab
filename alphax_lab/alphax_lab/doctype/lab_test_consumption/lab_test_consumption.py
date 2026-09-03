# Copyright (c) 2026, Neotec Integrated Solutions and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class LabTestConsumption(Document):
	def validate(self):
		self.validate_rows()
		self.validate_not_bundled()

	def validate_rows(self):
		if not self.consumables:
			frappe.throw(_("Add at least one consumable, or set Is Active to 0."))

		seen = {}
		for row in self.consumables:
			if flt(row.qty) <= 0:
				frappe.throw(_("Row {0}: qty must be greater than zero.").format(row.idx))
			if row.item == self.item:
				frappe.throw(_("Row {0}: a test cannot consume itself.").format(row.idx))
			if row.item in seen:
				frappe.throw(
					_("Row {0}: {1} is already on row {2}. Combine them into one row.").format(
						row.idx, frappe.bold(row.item), seen[row.item]
					)
				)
			seen[row.item] = row.idx

			if not frappe.get_cached_value("Item", row.item, "is_stock_item"):
				frappe.throw(
					_("Row {0}: {1} is not a stock item, so no quantity can be reduced.").format(
						row.idx, frappe.bold(row.item)
					)
				)

	def validate_not_bundled(self):
		"""A Product Bundle on the test item would consume stock through Packed
		Items as well as through this app, double counting."""
		if frappe.db.exists("Product Bundle", {"new_item_code": self.item, "disabled": 0}):
			frappe.throw(
				_("Item {0} has an active Product Bundle. Disable it first, otherwise consumption is booked twice.").format(
					frappe.bold(self.item)
				),
				title=_("Double Consumption Risk"),
			)
