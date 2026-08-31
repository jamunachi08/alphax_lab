# Copyright (c) 2026, Neotec Integrated Solutions and contributors
# For license information, please see license.txt

app_name = "alphax_lab"
app_title = "AlphaX Lab"
app_publisher = "Neotec Integrated Solutions"
app_description = "Lab consumable consumption for Plasma-integrated lab operations"
app_email = "support@neotec.sa"
app_license = "Commercial"
required_apps = ["erpnext"]

after_install = "alphax_lab.setup.install.after_install"
after_migrate = "alphax_lab.setup.install.after_migrate"

doc_events = {
	"Sales Invoice": {
		"validate": "alphax_lab.lab.consumption.validate",
		"on_submit": "alphax_lab.lab.consumption.on_submit",
		"on_cancel": "alphax_lab.lab.consumption.on_cancel",
	},
	"Delivery Note": {
		"validate": "alphax_lab.lab.consumption.validate",
		"on_submit": "alphax_lab.lab.consumption.on_submit",
		"on_cancel": "alphax_lab.lab.consumption.on_cancel",
	},
}
