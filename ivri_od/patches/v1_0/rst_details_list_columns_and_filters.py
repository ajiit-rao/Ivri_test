"""RST Details list: set the column order shown to staff.

The column order is kept in the List View Settings of the DocType (the form layout is not touched).
Filters are set in rst_details_list.js and the DocType JSON."""

import json

import frappe

DOCTYPE = "RST Details"
ORDER = [
	"rst_no",
	"vehicle_no",
	"tp_no",
	"party_name",
	"place",
	"commodity",
	"gross_vehicle_weight_qt",  # Load Wt
	"tare_vehicle_weight_qt",  # Tare Wt
	"gross_paddy_weight_qt",  # Gross Wt
	"gunny_weight_qt",
	"deduction_qt",  # Deduction as Dust
	"net_paddy_weight_qt",
	"entry_datetime",  # Date & Time, last
]


def execute():
	meta = frappe.get_meta(DOCTYPE)
	fields = [{"fieldname": name, "label": meta.get_label(name)} for name in ORDER]
	if frappe.db.exists("List View Settings", DOCTYPE):
		settings = frappe.get_doc("List View Settings", DOCTYPE)
		settings.fields = json.dumps(fields)
		settings.save(ignore_permissions=True)
	else:
		settings = frappe.new_doc("List View Settings")
		settings.name = DOCTYPE
		settings.fields = json.dumps(fields)
		settings.insert(ignore_permissions=True)
	frappe.clear_cache(doctype=DOCTYPE)
