#!/usr/bin/env python3
# Copyright (c) 2026, Neotec Integrated Solutions and contributors
"""Structural guard for alphax_lab. Run before every commit.

    python verify_tree.py
"""

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).parent
PKG = ROOT / "alphax_lab"
APP = PKG / "alphax_lab"

REQUIRED_FILES = [
	"pyproject.toml",
	"README.md",
	"INSTALL.md",
	"alphax_lab/__init__.py",
	"alphax_lab/hooks.py",
	"alphax_lab/modules.txt",
	"alphax_lab/lab/consumption.py",
	"alphax_lab/lab/batch_selection.py",
	"alphax_lab/setup/install.py",
	"alphax_lab/alphax_lab/report/lab_consumption_variance/lab_consumption_variance.py",
	"alphax_lab/alphax_lab/report/unconfigured_lab_items/unconfigured_lab_items.py",
	"alphax_lab/alphax_lab/report/lab_test_consumables/lab_test_consumables.py",
	"alphax_lab/demo/demo_data.py",
	"alphax_lab/patches.txt",
	"alphax_lab/patches/v0_4_0/migrate_consumables_to_doctype.py",
	"tests/test_consumption_plan.py",
]

REQUIRED_DOCTYPES = [
	"lab_test_consumption",
	"lab_consumable_item",
	"lab_item_group_filter",
	"lab_sample_type",
	"lab_consumption_settings",
	"plasma_test_map",
]

REQUIRED_HOOKS = [
	"alphax_lab.lab.consumption.validate",
	"alphax_lab.lab.consumption.before_submit",
	"alphax_lab.lab.consumption.on_submit",
	"alphax_lab.lab.consumption.on_cancel",
	"alphax_lab.setup.install.after_install",
	"alphax_lab.setup.install.after_migrate",
]

errors = []


def check_files():
	for rel in REQUIRED_FILES:
		if not (ROOT / rel).exists():
			errors.append(f"missing file: {rel}")


def check_doctypes():
	for slug in REQUIRED_DOCTYPES:
		folder = APP / "doctype" / slug
		if not folder.is_dir():
			errors.append(f"missing doctype folder: {slug}")
			continue
		for suffix in (".json", ".py", "__init__.py"):
			name = f"{slug}{suffix}" if suffix != "__init__.py" else suffix
			if not (folder / name).exists():
				errors.append(f"missing {name} in doctype/{slug}")
		json_path = folder / f"{slug}.json"
		if json_path.exists():
			try:
				meta = json.loads(json_path.read_text())
			except json.JSONDecodeError as exc:
				errors.append(f"invalid JSON in {slug}.json: {exc}")
				continue
			if meta.get("module") != "Alphax Lab":
				errors.append(f"{slug}.json module must be 'Alphax Lab'")


def check_hooks():
	text = (PKG / "hooks.py").read_text() if (PKG / "hooks.py").exists() else ""
	for path in REQUIRED_HOOKS:
		if path not in text:
			errors.append(f"hooks.py does not wire: {path}")


def check_no_server_scripts():
	"""House rule: all logic lives in versioned controllers."""
	for path in ROOT.rglob("*.json"):
		try:
			data = json.loads(path.read_text())
		except (json.JSONDecodeError, UnicodeDecodeError):
			continue
		if isinstance(data, dict) and data.get("doctype") == "Server Script":
			errors.append(f"Server Script fixture found: {path.relative_to(ROOT)}")


def check_frappe_dependencies():
	"""Frappe Cloud rejects the app at deploy time without this block."""
	import tomllib

	data = tomllib.loads((ROOT / "pyproject.toml").read_text())
	deps = data.get("tool", {}).get("bench", {}).get("frappe-dependencies")
	if not deps:
		errors.append("pyproject.toml missing [tool.bench.frappe-dependencies]")
		return
	if "frappe" not in deps:
		errors.append("[tool.bench.frappe-dependencies] missing 'frappe' pin")
	if "erpnext" not in deps:
		errors.append("[tool.bench.frappe-dependencies] missing 'erpnext' pin")


def check_no_vendor_strings():
	"""Product is white-labelled: no vendor name in user-facing strings.

	The functional dependency (hooks.required_apps, the pyproject pin) is
	deliberately exempt; the app will not install or run without it.
	"""
	exempt = {ROOT / "pyproject.toml", PKG / "hooks.py", ROOT / "verify_tree.py"}
	for pattern in ("*.py", "*.json", "*.js", "*.md"):
		for path in ROOT.rglob(pattern):
			if path in exempt or "__pycache__" in str(path):
				continue
			if "ERPNext" in path.read_text():
				errors.append(f"vendor name in user-facing file: {path.relative_to(ROOT)}")


def check_bundle_guard():
	"""The Product Bundle double-consumption guard must not be removed."""
	for slug in ("plasma_test_map", "lab_test_consumption"):
		src = (APP / "doctype" / slug / f"{slug}.py").read_text()
		if "Product Bundle" not in src:
			errors.append(f"{slug}.py lost the Product Bundle guard")


def check_patches_registered():
	"""patches.txt must carry BOTH section headers and list every patch on disk.

	Frappe reads [pre_model_sync] unconditionally, so an empty or missing header
	raises KeyError during install-app, even with no pre-sync patches. A patch
	module that is not listed silently never runs.
	"""
	import configparser

	patches_file = PKG / "patches.txt"
	listed = patches_file.read_text()

	parser = configparser.ConfigParser(allow_no_value=True)
	try:
		parser.read_string(listed)
	except configparser.Error as exc:
		errors.append(f"patches.txt is not valid configparser syntax: {exc}")
		return

	for section in ("pre_model_sync", "post_model_sync"):
		if not parser.has_section(section):
			errors.append(f"patches.txt missing required [{section}] header")

	patch_dir = PKG / "patches"
	if not patch_dir.is_dir():
		return
	for path in patch_dir.rglob("*.py"):
		if path.name == "__init__.py":
			continue
		dotted = ".".join(path.relative_to(PKG.parent).with_suffix("").parts)
		if dotted not in listed:
			errors.append(f"patch not registered in patches.txt: {dotted}")


def check_tabs():
	"""Frappe house style is tab indentation in Python. Docstrings are exempt."""
	fence = re.compile(r'"""|\'\'\'')
	for path in ROOT.rglob("*.py"):
		if path.name == "verify_tree.py":
			continue
		in_string = False
		for lineno, line in enumerate(path.read_text().splitlines(), 1):
			hits = len(fence.findall(line))
			if in_string:
				if hits % 2:
					in_string = False
				continue
			if hits % 2:
				in_string = True
				continue
			if re.match(r"^ {4}\S", line):
				errors.append(f"space indentation at {path.relative_to(ROOT)}:{lineno}")
				break


def main():
	check_files()
	check_doctypes()
	check_hooks()
	check_no_server_scripts()
	check_frappe_dependencies()
	check_no_vendor_strings()
	check_bundle_guard()
	check_patches_registered()
	check_tabs()

	version = _version()

	if errors:
		print(f"FAIL  (alphax_lab {version})")
		for err in errors:
			print(f"  - {err}")
		return 1

	print(f"OK: alphax_lab {version} structure verified")
	print(f"    patches.txt sections: {_patch_sections()}")
	return 0


def _version():
	init = (PKG / "__init__.py").read_text()
	match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', init)
	return match.group(1) if match else "unknown"


def _patch_sections():
	import configparser

	parser = configparser.ConfigParser(allow_no_value=True)
	try:
		parser.read_string((PKG / "patches.txt").read_text())
	except Exception:
		return "unreadable"
	return ", ".join(parser.sections()) or "none"


if __name__ == "__main__":
	sys.exit(main())
