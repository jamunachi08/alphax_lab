# Copyright (c) 2026, Neotec Integrated Solutions and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint


class LabConsumptionSettings(Document):
	def validate(self):
		self.warn_on_double_document_scope()

	def warn_on_double_document_scope(self):
		if cint(self.consume_on_delivery_note) and cint(self.consume_on_sales_invoice):
			frappe.msgprint(
				_("Both Delivery Note and Sales Invoice are set to consume. If a visit produces both documents, consumables will be issued twice."),
				indicator="orange",
				title=_("Check Integration Scope"),
			)
