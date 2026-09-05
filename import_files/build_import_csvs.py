#!/usr/bin/env python3
"""Generate Data Import CSVs for a lab starter catalog.

    python build_import_csvs.py <output_dir>

Produces files that import through Setup > Data Import, in the order they are
numbered. No shell access required on the site.
"""

import csv
import datetime
import pathlib
import sys

TODAY = datetime.date.today()


def d(days):
	return (TODAY + datetime.timedelta(days=days)).isoformat()


# ---------------------------------------------------------------------------
# consumables: code, name, uom, batched, opening qty, rate
# ---------------------------------------------------------------------------

CONSUMABLES = [
	# draw and collection
	("CONS-NEEDLE-21G", "Needle 21G x 1.5in", "Nos", False, 500, 0.45),
	("CONS-NEEDLE-23G", "Needle 23G x 1in", "Nos", False, 300, 0.45),
	("CONS-BUTTERFLY-23G", "Butterfly Needle 23G", "Nos", False, 200, 1.80),
	("CONS-SYRINGE-5ML", "Syringe 5ml", "Nos", False, 300, 0.90),
	("CONS-COTTON-BALL", "Cotton Ball", "Nos", False, 2000, 0.05),
	("CONS-ALCOHOL-SWAB", "Alcohol Swab", "Nos", False, 2000, 0.08),
	("CONS-GLOVES-NITRILE", "Nitrile Gloves (pair)", "Nos", False, 1000, 0.35),
	("CONS-TOURNIQUET", "Tourniquet (disposable)", "Nos", False, 200, 1.20),
	("CONS-PLASTER", "Adhesive Plaster", "Nos", False, 1000, 0.06),
	# containers
	("CONS-TUBE-EDTA", "EDTA Tube 3ml (lavender)", "Nos", False, 800, 0.55),
	("CONS-TUBE-SST", "SST Serum Tube 5ml (gold)", "Nos", False, 800, 0.75),
	("CONS-TUBE-FLUORIDE", "Fluoride Tube 2ml (grey)", "Nos", False, 300, 0.60),
	("CONS-TUBE-CITRATE", "Citrate Tube 2.7ml (blue)", "Nos", False, 200, 0.65),
	("CONS-CUP-URINE", "Urine Cup 60ml", "Nos", False, 400, 0.40),
	# lab disposables
	("CONS-TIP-200UL", "Pipette Tip 200ul", "Nos", False, 2000, 0.03),
	("CONS-TIP-1000UL", "Pipette Tip 1000ul", "Nos", False, 1000, 0.05),
	("CONS-CUVETTE", "Reaction Cuvette", "Nos", False, 2000, 0.12),
	("CONS-SLIDE", "Microscope Slide", "Nos", False, 500, 0.10),
	# batched: reagents, controls, calibrators, strips
	("REAG-CBC", "CBC Reagent Pack", "Nos", True, 0, 180.00),
	("REAG-ESR", "ESR Reagent", "Nos", True, 0, 95.00),
	("REAG-GLUCOSE", "Glucose Reagent", "Nos", True, 0, 120.00),
	("REAG-HBA1C", "HbA1c Reagent Kit", "Nos", True, 0, 320.00),
	("REAG-LIPID", "Lipid Panel Reagent Set", "Nos", True, 0, 260.00),
	("REAG-LFT", "LFT Reagent Set", "Nos", True, 0, 240.00),
	("REAG-RFT", "RFT Reagent Set", "Nos", True, 0, 230.00),
	("REAG-TSH", "TSH Reagent Kit", "Nos", True, 0, 410.00),
	("REAG-VITD", "Vitamin D Reagent Kit", "Nos", True, 0, 480.00),
	("REAG-CRP", "CRP Reagent", "Nos", True, 0, 175.00),
	("REAG-BLOODGRP", "Anti-A/B/D Antisera Set", "Nos", True, 0, 140.00),
	("CTRL-HEMA", "Hematology Control Serum", "Nos", True, 0, 210.00),
	("CTRL-CHEM", "Chemistry Control Serum", "Nos", True, 0, 195.00),
	("STRIP-URINE", "Urine Dipstick 10-parameter", "Nos", True, 0, 1.60),
]

# batched item -> [(batch suffix, days to expiry, qty)]
BATCHES = {
	"REAG-CBC": [("A", 60, 12), ("B", 400, 20)],
	"REAG-ESR": [("A", 90, 8), ("B", 365, 12)],
	"REAG-GLUCOSE": [("A", 75, 10), ("B", 380, 15)],
	"REAG-HBA1C": [("A", 120, 6), ("B", 420, 10)],
	"REAG-LIPID": [("A", 55, 8), ("B", 390, 12)],
	"REAG-LFT": [("A", 45, 10), ("B", 410, 14)],
	"REAG-RFT": [("A", 70, 10), ("B", 395, 14)],
	"REAG-TSH": [("A", 110, 5), ("B", 430, 9)],
	"REAG-VITD": [("A", 130, 5), ("B", 440, 8)],
	"REAG-CRP": [("A", 65, 8), ("B", 370, 12)],
	"REAG-BLOODGRP": [("A", 95, 6), ("B", 360, 10)],
	"CTRL-HEMA": [("A", 40, 4), ("B", 300, 8)],
	"CTRL-CHEM": [("A", 50, 4), ("B", 310, 8)],
	"STRIP-URINE": [("A", 85, 200), ("B", 400, 300)],
}

# Shared blocks, expanded per test below. Every test lists its full set: there
# are no shared tiers at runtime.
VENOUS_DRAW = [
	("CONS-NEEDLE-21G", 1),
	("CONS-COTTON-BALL", 2),
	("CONS-ALCOHOL-SWAB", 1),
	("CONS-GLOVES-NITRILE", 1),
	("CONS-TOURNIQUET", 1),
	("CONS-PLASTER", 1),
]

TESTS = [
	{
		"code": "LAB-CBC",
		"name": "Complete Blood Count (CBC)",
		"rate": 45,
		"sample_type": "Whole Blood EDTA",
		"consumables": VENOUS_DRAW
		+ [("CONS-TUBE-EDTA", 1), ("CONS-TIP-200UL", 2), ("REAG-CBC", 1), ("CTRL-HEMA", 0.05)],
	},
	{
		"code": "LAB-ESR",
		"name": "ESR",
		"rate": 25,
		"sample_type": "Whole Blood EDTA",
		"consumables": VENOUS_DRAW + [("CONS-TUBE-EDTA", 1), ("REAG-ESR", 1)],
	},
	{
		"code": "LAB-BLOODGRP",
		"name": "Blood Group and Rh",
		"rate": 35,
		"sample_type": "Whole Blood EDTA",
		"consumables": VENOUS_DRAW
		+ [("CONS-TUBE-EDTA", 1), ("CONS-SLIDE", 1), ("REAG-BLOODGRP", 1)],
	},
	{
		"code": "LAB-FBS",
		"name": "Fasting Blood Sugar",
		"rate": 20,
		"sample_type": "Serum",
		"consumables": VENOUS_DRAW
		+ [("CONS-TUBE-FLUORIDE", 1), ("CONS-CUVETTE", 1), ("CONS-TIP-200UL", 1), ("REAG-GLUCOSE", 1)],
	},
	{
		"code": "LAB-HBA1C",
		"name": "HbA1c",
		"rate": 85,
		"sample_type": "Whole Blood EDTA",
		"consumables": VENOUS_DRAW
		+ [("CONS-TUBE-EDTA", 1), ("CONS-TIP-200UL", 2), ("REAG-HBA1C", 1), ("CTRL-CHEM", 0.05)],
	},
	{
		"code": "LAB-LIPID",
		"name": "Lipid Profile",
		"rate": 95,
		"sample_type": "Serum",
		"consumables": VENOUS_DRAW
		+ [("CONS-TUBE-SST", 1), ("CONS-CUVETTE", 4), ("CONS-TIP-200UL", 4), ("REAG-LIPID", 1), ("CTRL-CHEM", 0.05)],
	},
	{
		"code": "LAB-LFT",
		"name": "Liver Function Test",
		"rate": 90,
		"sample_type": "Serum",
		"consumables": VENOUS_DRAW
		+ [("CONS-TUBE-SST", 1), ("CONS-CUVETTE", 5), ("CONS-TIP-200UL", 5), ("REAG-LFT", 1), ("CTRL-CHEM", 0.05)],
	},
	{
		"code": "LAB-RFT",
		"name": "Renal Function Test",
		"rate": 90,
		"sample_type": "Serum",
		"consumables": VENOUS_DRAW
		+ [("CONS-TUBE-SST", 1), ("CONS-CUVETTE", 4), ("CONS-TIP-200UL", 4), ("REAG-RFT", 1), ("CTRL-CHEM", 0.05)],
	},
	{
		"code": "LAB-TSH",
		"name": "TSH",
		"rate": 110,
		"sample_type": "Serum",
		"consumables": VENOUS_DRAW
		+ [("CONS-TUBE-SST", 1), ("CONS-TIP-200UL", 2), ("REAG-TSH", 1), ("CTRL-CHEM", 0.05)],
	},
	{
		"code": "LAB-VITD",
		"name": "Vitamin D (25-OH)",
		"rate": 160,
		"sample_type": "Serum",
		"consumables": VENOUS_DRAW
		+ [("CONS-TUBE-SST", 1), ("CONS-TIP-200UL", 2), ("REAG-VITD", 1)],
	},
	{
		"code": "LAB-CRP",
		"name": "C-Reactive Protein",
		"rate": 70,
		"sample_type": "Serum",
		"consumables": VENOUS_DRAW
		+ [("CONS-TUBE-SST", 1), ("CONS-CUVETTE", 1), ("CONS-TIP-200UL", 1), ("REAG-CRP", 1)],
	},
	{
		"code": "LAB-URINE",
		"name": "Urine Routine",
		"rate": 30,
		"sample_type": "Urine",
		"consumables": [
			("CONS-GLOVES-NITRILE", 1),
			("CONS-CUP-URINE", 1),
			("STRIP-URINE", 1),
			("CONS-SLIDE", 1),
		],
	},
]

WAREHOUSE = "Lab Store - {abbr}"


def write(path, header, rows):
	with open(path, "w", newline="", encoding="utf-8-sig") as fh:
		writer = csv.writer(fh)
		writer.writerow(header)
		writer.writerows(rows)
	print(f"  {path.name:44} {len(rows)} rows")


def main(outdir):
	out = pathlib.Path(outdir)
	out.mkdir(parents=True, exist_ok=True)
	print("\nGenerating Data Import files:\n")

	# 1. consumable items
	rows = []
	for code, name, uom, batched, _qty, _rate in CONSUMABLES:
		rows.append(
			[
				code,
				name,
				"Lab Consumables",
				uom,
				1,
				0,
				1,
				1 if batched else 0,
				1 if batched else 0,
				1 if batched else 0,
				f"{code}-.####" if batched else "",
			]
		)
	write(
		out / "01_items_consumables.csv",
		[
			"item_code",
			"item_name",
			"item_group",
			"stock_uom",
			"is_stock_item",
			"is_sales_item",
			"is_purchase_item",
			"has_batch_no",
			"has_expiry_date",
			"create_new_batch",
			"batch_number_series",
		],
		rows,
	)

	# 2. test items
	rows = [
		[t["code"], t["name"], "Lab Tests", "Nos", 0, 1, 0]
		for t in TESTS
	]
	write(
		out / "02_items_tests.csv",
		["item_code", "item_name", "item_group", "stock_uom", "is_stock_item", "is_sales_item", "is_purchase_item"],
		rows,
	)

	# 3. batches
	rows = []
	for item_code, batches in BATCHES.items():
		for suffix, days, _qty in batches:
			rows.append([f"{item_code}-{suffix}", item_code, d(days)])
	write(out / "03_batches.csv", ["batch_id", "item", "expiry_date"], rows)

	# 4. lab test consumption, parent + child rows
	#
	# Data Import groups a parent with its child rows by leaving the parent
	# columns BLANK on continuation rows. Repeating the parent value on every
	# row would create one record per row instead.
	rows = []
	for test in TESTS:
		for idx, (code, qty) in enumerate(test["consumables"]):
			rows.append(
				[
					test["code"] if idx == 0 else "",
					1 if idx == 0 else "",
					code,
					qty,
				]
			)
	write(
		out / "04_lab_test_consumption.csv",
		["item", "is_active", "consumables.item", "consumables.qty"],
		rows,
	)

	# 5. plasma test map
	rows = [
		[t["name"], t["code"], t["code"], t["sample_type"], 1]
		for t in TESTS
	]
	write(
		out / "05_plasma_test_map.csv",
		["plasma_test_name", "plasma_test_code", "item", "sample_type", "is_active"],
		rows,
	)

	# 6. opening stock, Stock Entry Material Receipt with batches
	rows = []
	first = True
	for code, _name, _uom, batched, qty, rate in CONSUMABLES:
		if batched:
			for suffix, _days, bqty in BATCHES[code]:
				rows.append(_stock_row(first, code, bqty, rate, f"{code}-{suffix}"))
				first = False
		elif qty:
			rows.append(_stock_row(first, code, qty, rate, ""))
			first = False
	write(
		out / "06_opening_stock.csv",
		[
			"stock_entry_type",
			"purpose",
			"company",
			"items.item_code",
			"items.qty",
			"items.basic_rate",
			"items.t_warehouse",
			"items.use_serial_batch_fields",
			"items.batch_no",
		],
		rows,
	)

	print(f"\n  {len(TESTS)} tests, {len(CONSUMABLES)} consumables, "
	      f"{sum(len(b) for b in BATCHES.values())} batches\n")


def _stock_row(first, code, qty, rate, batch):
	return [
		"Material Receipt" if first else "",
		"Material Receipt" if first else "",
		"<YOUR COMPANY>" if first else "",
		code,
		qty,
		rate,
		"<LAB STORE WAREHOUSE>",
		1 if batch else 0,
		batch,
	]


if __name__ == "__main__":
	main(sys.argv[1] if len(sys.argv) > 1 else "import_files")
