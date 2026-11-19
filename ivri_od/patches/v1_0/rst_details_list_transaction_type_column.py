"""RST Details list: show the Transaction Type column just before the Vehicle No column.

The column order is kept in the List View Settings of the DocType. This patch only adds Transaction
Type if it is missing, so any other column change made by staff is kept."""

import json

import frappe

DOCTYPE = "RST Details"
COLUMN = "transaction_type"
BEFORE = "vehicle_no"


def execute():
	if not frappe.db.exists("List View Settings", DOCTYPE):
		return  # the column order patch creates it; nothing to change here

	settings = frappe.get_doc("List View Settings", DOCTYPE)
	fields = json.loads(settings.fields or "[]")
	if any(f.get("fieldname") == COLUMN for f in fields):
		return

	names = [f.get("fieldname") for f in fields]
	index = names.index(BEFORE) if BEFORE in names else len(fields)
	fields.insert(index, {"fieldname": COLUMN, "label": frappe.get_meta(DOCTYPE).get_label(COLUMN)})

	settings.fields = json.dumps(fields)
	settings.save(ignore_permissions=True)
	frappe.clear_cache(doctype=DOCTYPE)
