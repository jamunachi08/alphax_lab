// Copyright (c) 2026, Neotec Integrated Solutions and contributors
// For license information, please see license.txt

frappe.query_reports["Lab Test Consumables"] = {
	filters: [
		{
			fieldname: "test_item",
			label: __("Test Item"),
			fieldtype: "Link",
			options: "Item",
		},
		{
			fieldname: "warehouse",
			label: __("Lab Store Warehouse"),
			fieldtype: "Link",
			options: "Warehouse",
		},
	],
	tree: true,
	name_field: "test_item",
	parent_field: "parent_test",
	initial_depth: 1,
};
