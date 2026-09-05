#!/usr/bin/env python3
# Copyright (c) 2026, Neotec Integrated Solutions and contributors
"""Batch allocation tests. No bench or database needed.

    python tests/test_batch_selection.py

Regression guarded here: v15 holds batch quantities either on
Stock Ledger Entry.batch_no or inside Serial and Batch Bundle entries. Reading
only one made 500 units of stock invisible and reported a phantom shortage.
"""

import datetime
import pathlib
import sys
import types

LEGACY = []
BUNDLE = []
BATCHES = [
	{"name": "STRIP-A", "expiry_date": datetime.date(2026, 11, 29), "creation": 1, "disabled": 0},
	{"name": "STRIP-B", "expiry_date": datetime.date(2027, 10, 10), "creation": 2, "disabled": 0},
]


class _D(dict):
	__getattr__ = dict.get


def install_stubs():
	f = types.ModuleType("frappe")
	f._dict = _D
	f.bold = lambda x: x
	f._ = lambda s: s
	f.get_cached_value = lambda dt, n, fld: 1
	f.get_all = lambda dt, filters=None, fields=None, **k: [_D(b) for b in BATCHES]
	f.whitelist = lambda *a, **k: (lambda fn: fn)

	def sql(q, params=None, as_dict=False):
		return [_D(r) for r in (BUNDLE if "Serial and Batch Entry" in q else LEGACY)]

	f.db = types.SimpleNamespace(sql=sql, table_exists=lambda t: True)
	sys.modules["frappe"] = f

	u = types.ModuleType("frappe.utils")
	u.flt = lambda v, precision=None: (
		round(float(v or 0), precision) if precision is not None else float(v or 0)
	)
	u.getdate = lambda x=None: x if isinstance(x, datetime.date) else datetime.date(2026, 9, 5)
	u.nowdate = lambda: datetime.date(2026, 9, 5)
	sys.modules["frappe.utils"] = u


def main():
	install_stubs()
	sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
	from alphax_lab.lab import batch_selection as bs

	failures = []

	def check(label, condition):
		print(f"  {'PASS' if condition else 'FAIL'}  {label}")
		if not condition:
			failures.append(label)

	print("stock held only in Serial and Batch Bundle")
	BUNDLE[:] = [{"batch_no": "STRIP-A", "qty": 200}, {"batch_no": "STRIP-B", "qty": 300}]
	LEGACY[:] = []
	alloc, short = bs.allocate("STRIP", "Stores - A", 1)
	check("bundle stock is visible", short == 0)
	check("nearest expiry picked", alloc[0]["batch_no"] == "STRIP-A")

	print("stock held only on Stock Ledger Entry")
	BUNDLE[:] = []
	LEGACY[:] = [{"batch_no": "STRIP-A", "qty": 200}, {"batch_no": "STRIP-B", "qty": 300}]
	alloc, short = bs.allocate("STRIP", "Stores - A", 1)
	check("legacy stock is visible", short == 0)

	print("both paths, split across batches")
	LEGACY[:] = [{"batch_no": "STRIP-A", "qty": 150}]
	BUNDLE[:] = [{"batch_no": "STRIP-A", "qty": 50}, {"batch_no": "STRIP-B", "qty": 300}]
	alloc, short = bs.allocate("STRIP", "Stores - A", 250)
	check("quantities from both paths sum", short == 0)
	check(
		"requirement splits across two batches",
		alloc == [{"qty": 200.0, "batch_no": "STRIP-A"}, {"qty": 50.0, "batch_no": "STRIP-B"}],
	)

	print("genuine shortage")
	LEGACY[:] = []
	BUNDLE[:] = []
	alloc, short = bs.allocate("STRIP", "Stores - A", 1)
	check("shortage still reported", short == 1.0)
	check("message names the cause", "no batch holds stock" in bs.describe_shortage("STRIP", "Stores - A", 1, short))

	print("expired batches only")
	BATCHES[0]["expiry_date"] = datetime.date(2026, 1, 1)
	BATCHES[1]["expiry_date"] = datetime.date(2026, 2, 1)
	BUNDLE[:] = [{"batch_no": "STRIP-A", "qty": 200}, {"batch_no": "STRIP-B", "qty": 300}]
	alloc, short = bs.allocate("STRIP", "Stores - A", 1)
	check("expired stock not allocated", short == 1.0)
	check("message says expired", "expired" in bs.describe_shortage("STRIP", "Stores - A", 1, short))
	alloc, short = bs.allocate("STRIP", "Stores - A", 1, allow_expired=True)
	check("allow_expired overrides", short == 0)

	print()
	if failures:
		print(f"FAILED: {len(failures)}")
		return 1
	print("All checks passed")
	return 0


if __name__ == "__main__":
	sys.exit(main())
