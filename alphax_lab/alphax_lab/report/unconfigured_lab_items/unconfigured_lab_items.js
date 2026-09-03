// Copyright (c) 2026, Neotec Integrated Solutions and contributors
// For license information, please see license.txt

frappe.query_reports["Unconfigured Lab Items"] = {
	filters: [
		{
			fieldname: "include_disabled",
			label: __("Include Disabled Items"),
			fieldtype: "Check",
			default: 0,
		},
	],
};
