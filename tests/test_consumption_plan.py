#!/usr/bin/env python3
# Copyright (c) 2026, Neotec Integrated Solutions and contributors
"""Standalone tests for the three-tier consumption plan builder.

Runs without a bench or database — frappe is stubbed with fixture data, so this
can go in CI ahead of any site being available.

    python tests/test_consumption_plan.py
"""

import sys
import types
import pathlib

MAPS = {
	"LAB-CBC": {"name": "CBC", "sample_type": "Whole Blood EDTA", "requires_venipuncture": 1},
	"LAB-LFT": {"name": "LFT", "sample_type": "Serum", "requires_venipuncture": 1},
	"LAB-URINE": {"name": "Urine Routine", "sample_type": "Urine", "requires_venipuncture": 0},
}

CONSUMABLES = {
	"LAB-CBC": [{"item": "REG-CBC", "qty": 1}, {"item": "CTRL-CBC", "qty": 0.05}],
	"LAB-LFT": [{"item": "REG-LFT", "qty": 1}, {"item": "CUVETTE", "qty": 4}],
	"LAB-URINE": [{"item": "DIPSTICK", "qty": 1}],
	"KIT-VENI": [
		{"item": "NEEDLE-21G", "qty": 1},
		{"item": "COTTON", "qty": 2},
		{"item": "SWAB", "qty": 1},
		{"item": "GLOVES", "qty": 1},
	],
	"CONT-EDTA": [{"item": "TUBE-EDTA", "qty": 1}],
	"CONT-SERUM": [{"item": "TUBE-SERUM", "qty": 1}],
	"CONT-URINE": [{"item": "CUP-URINE", "qty": 1}],
}

CONTAINERS = {
	"Whole Blood EDTA": "CONT-EDTA",
	"Serum": "CONT-SERUM",
	"Urine": "CONT-URINE",
}


class _D(dict):
	__getattr__ = dict.get


def install_stubs():
	f = types.ModuleType("frappe")
	f._dict = _D

	def get_all(dt, filters=None, fields=None, order_by=None, limit=None, pluck=None):
		filters = filters or {}
		if dt == "Plasma Test Map":
			m = MAPS.get(filters.get("item"))
			return [_D(m)] if m else []
		if dt == "Lab Consumable Item":
			return [_D(r) for r in CONSUMABLES.get(filters.get("parent"), [])]
		return []

	f.get_all = get_all
	f.get_cached_value = lambda dt, name, field: (
		CONTAINERS.get(name) if dt == "Lab Sample Type" else "Nos"
	)
	f.throw = lambda *a, **k: None
	f.msgprint = lambda *a, **k: None
	f.bold = lambda x: x
	f.new_doc = lambda *a: None
	f.get_doc = lambda *a, **k: None
	f.get_cached_doc = lambda *a: None
	f.get_single = lambda *a: None
	f.log_error = lambda *a, **k: None
	f.whitelist = lambda *a, **k: (lambda fn: fn)

	class DNE(Exception):
		pass

	f.DoesNotExistError = DNE
	f.db = types.SimpleNamespace(sql=lambda *a, **k: [], exists=lambda *a, **k: False)
	f.utils = types.SimpleNamespace(get_link_to_form=lambda *a: "")
	f._ = lambda s: s
	sys.modules["frappe"] = f

	u = types.ModuleType("frappe.utils")
	u.cint = int
	u.flt = float
	u.getdate = lambda x=None: x
	u.nowdate = lambda: "2026-08-30"
	sys.modules["frappe.utils"] = u

	sys.modules["frappe.model"] = types.ModuleType("frappe.model")
	mdd = types.ModuleType("frappe.model.document")

	class Document:
		pass

	mdd.Document = Document
	sys.modules["frappe.model.document"] = mdd


class Row:
	def __init__(self, code, qty):
		self.item_code = code
		self.qty = qty


class Doc(dict):
	def __init__(self, items, is_return=0):
		self._items = items
		self["is_return"] = is_return

	def get(self, key, default=None):
		if key == "items":
			return self._items
		return dict.get(self, key, default)


def main():
	install_stubs()
	sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
	from alphax_lab.lab import consumption

	settings = _D({"venipuncture_item": "KIT-VENI"})
	failures = []

	def check(label, condition):
		print(f"  {'PASS' if condition else 'FAIL'}  {label}")
		if not condition:
			failures.append(label)

	print("single test, single sample type")
	plan, _ = consumption.build_plan(Doc([Row("LAB-CBC", 1)]), settings)
	check("one needle", plan.get("NEEDLE-21G") == 1)
	check("one EDTA tube", plan.get("TUBE-EDTA") == 1)
	check("fractional control qty preserved", plan.get("CTRL-CBC") == 0.05)

	print("three tests, one draw, two blood sample types")
	plan, _ = consumption.build_plan(
		Doc([Row("LAB-CBC", 1), Row("LAB-LFT", 1), Row("LAB-URINE", 1)]), settings
	)
	check("venipuncture kit issued once", plan.get("NEEDLE-21G") == 1)
	check("cotton not multiplied per test", plan.get("COTTON") == 2)
	check("one container per sample type", plan.get("TUBE-EDTA") == 1 and plan.get("TUBE-SERUM") == 1)
	check("urine cup issued", plan.get("CUP-URINE") == 1)

	print("repeat run, line qty 2")
	plan, _ = consumption.build_plan(Doc([Row("LAB-CBC", 2)]), settings)
	check("reagents scale with line qty", plan.get("REG-CBC") == 2)
	check("kit does not scale with line qty", plan.get("NEEDLE-21G") == 1)

	print("no venipuncture required")
	plan, _ = consumption.build_plan(Doc([Row("LAB-URINE", 1)]), settings)
	check("no needle for urine-only", "NEEDLE-21G" not in plan)

	print("unmapped item")
	plan, _ = consumption.build_plan(Doc([Row("SERVICE-CONSULT", 1)]), settings)
	check("empty plan, no consumption", not plan)

	print()
	if failures:
		print(f"FAILED: {len(failures)}")
		return 1
	print("All checks passed")
	return 0


if __name__ == "__main__":
	sys.exit(main())
