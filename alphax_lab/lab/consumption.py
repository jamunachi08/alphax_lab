# Copyright (c) 2026, Neotec Integrated Solutions and contributors
# For license information, please see license.txt

"""Lab consumable consumption for Plasma-integrated sales documents.

Plasma sends test-level lines only (e.g. "CBC"). The billing document stays a
faithful mirror of what Plasma billed: no injected lines, no zero-rate rows, no
Packed Items, nothing extra in the ZATCA XML or on the printed invoice.

Each test Item carries its own complete Lab Consumables child table. Consumption
is the sum of every mapped line's consumables, multiplied by that line's qty.
There are no shared or document-level tiers: what a test consumes is defined
once, on the test.

The plan is booked as a Material Issue Stock Entry on submit, linked back to the
source document, and reversed on cancel. This fires the same way whether the
document was typed by a user, created by Data Import, or posted over the API,
because it is driven by the submit event rather than the entry channel.
"""

from collections import OrderedDict

import frappe
from frappe import _
from frappe.utils import cint, flt

from alphax_lab.lab import batch_selection

TARGET_DOCTYPES = ("Sales Invoice", "Delivery Note")


# ---------------------------------------------------------------------------
# hook entry points
# ---------------------------------------------------------------------------

def on_submit(doc, method=None):
	settings = get_settings()
	if not _in_scope(doc, settings):
		return

	if _existing_entry(doc):
		return

	plan, context = build_plan(doc)
	if not plan:
		return

	create_consumption_entry(doc, plan, context, settings)


def on_cancel(doc, method=None):
	"""Cancel the linked Stock Entry so stock returns to the lab store."""
	for name in _existing_entry(doc, all_matches=True):
		entry = frappe.get_doc("Stock Entry", name)
		if entry.docstatus == 1:
			entry.flags.ignore_permissions = True
			entry.cancel()


def validate(doc, method=None):
	"""Warn about lines that would consume nothing.

	Runs on every save, including drafts. Blocks only when the site is
	configured to Block on Save; otherwise it flags the problem and lets the
	draft stand, so reception can park a half-finished document.
	"""
	problems = find_unconfigured(doc)
	if not problems:
		return

	settings = get_settings()
	action = (settings.unconfigured_item_action or "Block on Submit") if settings else "Block on Submit"

	if action == "Block on Save":
		frappe.throw(_unconfigured_message(problems), title=_("Lab Consumption Not Configured"))
		return

	frappe.msgprint(
		_unconfigured_message(problems),
		title=_("Lab Consumption Not Configured"),
		indicator="orange",
	)


def before_submit(doc, method=None):
	"""Block the post. A submitted document that consumes nothing is the
	failure this app exists to prevent, and it is invisible after the fact."""
	problems = find_unconfigured(doc)
	if not problems:
		return

	settings = get_settings()
	action = (settings.unconfigured_item_action or "Block on Submit") if settings else "Block on Submit"

	if action == "Warn Only":
		frappe.msgprint(
			_unconfigured_message(problems),
			title=_("Lab Consumption Not Configured"),
			indicator="orange",
		)
		return

	frappe.throw(_unconfigured_message(problems), title=_("Lab Consumption Not Configured"))


def find_unconfigured(doc):
	"""Return [(item_code, reason)] for lines that would consume no stock.

	Two ways an item in a lab group fails: no active map, or a map with an
	empty consumable list. The second is easy to miss because the item looks
	configured until you open it.
	"""
	settings = get_settings()
	if not settings or not cint(settings.enabled):
		return []

	lab_groups = {d.item_group for d in settings.get("lab_item_groups", []) if d.item_group}
	if not lab_groups:
		return []

	problems = []
	seen = set()

	for row in doc.get("items", []):
		if not row.item_code or row.item_code in seen:
			continue
		if row.item_group not in lab_groups:
			continue
		seen.add(row.item_code)

		if not _get_map(row.item_code):
			problems.append((row.item_code, _("no active Plasma Test Map")))
		elif not _has_consumables(row.item_code):
			problems.append((row.item_code, _("Lab Consumables table is empty")))

	return problems


def _has_consumables(item_code):
	return bool(
		frappe.get_all(
			"Lab Consumable Item",
			filters={"parent": item_code, "parenttype": "Item"},
			limit=1,
		)
	)


def _unconfigured_message(problems):
	lines = "<br>".join(f"&bull; {frappe.bold(code)} &mdash; {reason}" for code, reason in problems)
	return _(
		"These lines would consume no stock:<br><br>{0}<br><br>"
		"Fix either way:<br>"
		"&bull; If it is a real test, add a Plasma Test Map row and fill its Lab Consumables table.<br>"
		"&bull; If it is not a lab test, move it to an item group that is not listed under "
		"Lab Item Groups in Lab Consumption Settings.<br><br>"
		"Run the <b>Unconfigured Lab Items</b> report to find every item in this state."
	).format(lines)


# ---------------------------------------------------------------------------
# plan
# ---------------------------------------------------------------------------

def build_plan(doc, settings=None):
	"""Return (plan, context).

	plan    OrderedDict of consumable item_code -> qty
	context dict of which tests drove the plan, for the Stock Entry remark

	Every mapped line contributes its own consumables scaled by line qty. Two
	tests that each list a needle consume two needles; that is intentional and
	is what the Lab Consumption Variance report is there to measure.
	"""
	plan = OrderedDict()
	context = {"tests": []}

	sign = -1 if cint(doc.get("is_return")) else 1

	for row in doc.get("items", []):
		if not row.item_code:
			continue

		if not _get_map(row.item_code):
			continue

		qty = flt(row.qty) * sign
		if qty <= 0:
			continue

		context["tests"].append(row.item_code)
		_add_consumables(plan, row.item_code, multiplier=qty)

	return OrderedDict((k, v) for k, v in plan.items() if flt(v) > 0), context


def _add_consumables(plan, parent_item, multiplier=1):
	rows = frappe.get_all(
		"Lab Consumable Item",
		filters={"parent": parent_item, "parenttype": "Item"},
		fields=["item", "qty"],
		order_by="idx asc",
	)
	for row in rows:
		if not row.item:
			continue
		plan[row.item] = flt(plan.get(row.item, 0)) + flt(row.qty) * flt(multiplier)


# ---------------------------------------------------------------------------
# stock entry
# ---------------------------------------------------------------------------

def create_consumption_entry(doc, plan, context, settings):
	is_return = cint(doc.get("is_return"))
	warehouse = settings.consumable_warehouse

	entry = frappe.new_doc("Stock Entry")
	entry.company = doc.company or settings.company
	entry.purpose = "Material Receipt" if is_return else "Material Issue"
	entry.stock_entry_type = "Material Receipt" if is_return else (settings.stock_entry_type or "Material Issue")
	entry.set_posting_time = 1
	entry.posting_date = doc.posting_date
	entry.posting_time = doc.get("posting_time")
	entry.source_doctype = doc.doctype
	entry.source_document = doc.name
	entry.plasma_ref = doc.get("plasma_ref")
	entry.remarks = _build_remark(doc, context)

	shortages = []

	for item_code, qty in plan.items():
		allocations, shortfall = batch_selection.allocate(
			item_code=item_code,
			warehouse=warehouse,
			qty=qty,
			posting_date=doc.posting_date,
			strategy=settings.batch_strategy or "Nearest Expiry",
			allow_expired=cint(settings.allow_expired_batches),
		)

		if shortfall > flt(settings.shortage_tolerance_qty):
			shortages.append(batch_selection.describe_shortage(item_code, warehouse, qty, shortfall))

		for allocation in allocations:
			_append_entry_row(entry, item_code, allocation, warehouse, is_return, settings)

	if shortages and cint(settings.block_on_shortage):
		frappe.throw(
			_("Insufficient lab consumables:<br>{0}").format("<br>".join(shortages)),
			title=_("Lab Store Shortage"),
		)

	if shortages:
		frappe.log_error(
			title="Lab consumption shortage",
			message=f"{doc.doctype} {doc.name}\n" + "\n".join(shortages),
		)

	if not entry.get("items"):
		return None

	entry.flags.ignore_permissions = True
	entry.insert()
	entry.submit()

	frappe.msgprint(
		_("Lab consumables issued: {0}").format(
			frappe.utils.get_link_to_form("Stock Entry", entry.name)
		),
		indicator="green",
		alert=True,
	)

	return entry.name


def _append_entry_row(entry, item_code, allocation, warehouse, is_return, settings):
	row = entry.append("items", {})
	row.item_code = item_code
	row.qty = flt(allocation["qty"])
	row.uom = frappe.get_cached_value("Item", item_code, "stock_uom")
	row.stock_uom = row.uom
	row.conversion_factor = 1

	if is_return:
		row.t_warehouse = warehouse
	else:
		row.s_warehouse = warehouse

	if allocation.get("batch_no"):
		row.use_serial_batch_fields = 1
		row.batch_no = allocation["batch_no"]

	if settings.consumable_expense_account:
		row.expense_account = settings.consumable_expense_account
	if settings.consumable_cost_center:
		row.cost_center = settings.consumable_cost_center


def _build_remark(doc, context):
	parts = [_("Lab consumables for {0} {1}").format(doc.doctype, doc.name)]
	if doc.get("plasma_ref"):
		parts.append(_("Plasma ref: {0}").format(doc.plasma_ref))
	if context.get("tests"):
		parts.append(_("Tests: {0}").format(", ".join(context["tests"])))
	return "\n".join(parts)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def get_settings():
	try:
		return frappe.get_cached_doc("Lab Consumption Settings")
	except frappe.DoesNotExistError:
		return None


def _in_scope(doc, settings):
	if doc.doctype not in TARGET_DOCTYPES:
		return False
	if not settings or not cint(settings.enabled):
		return False
	if not settings.consumable_warehouse:
		return False
	if doc.doctype == "Delivery Note" and not cint(settings.consume_on_delivery_note):
		return False
	if doc.doctype == "Sales Invoice" and not cint(settings.consume_on_sales_invoice):
		return False
	return True


def _get_map(item_code):
	if not item_code:
		return None
	rows = frappe.get_all(
		"Plasma Test Map",
		filters={"item": item_code, "is_active": 1},
		fields=["name", "sample_type"],
		limit=1,
	)
	return rows[0] if rows else None


def _existing_entry(doc, all_matches=False):
	names = frappe.get_all(
		"Stock Entry",
		filters={"source_doctype": doc.doctype, "source_document": doc.name, "docstatus": 1},
		pluck="name",
	)
	if all_matches:
		return names
	return names[0] if names else None


@frappe.whitelist()
def preview_plan(doctype, name):
	"""Read-only plan preview for the client script button."""
	doc = frappe.get_doc(doctype, name)
	doc.check_permission("read")
	plan, context = build_plan(doc)
	return {
		"plan": [{"item": k, "qty": flt(v, 6)} for k, v in plan.items()],
		"context": context,
	}
