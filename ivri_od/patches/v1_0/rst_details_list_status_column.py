"""RST Details list: show the Status column just before the Date & Time column.

The column order is kept in the List View Settings of the DocType. This patch only adds Status
(tp_status) if it is missing, so any other column change made by staff is kept.
The text shown in the column is set in rst_details_list.js."""

import json

import frappe

DOCTYPE = "RST Details"
STATUS = "tp_status"
BEFORE = "entry_datetime"  # Date & Time


def execute():
	meta = frappe.get_meta(DOCTYPE)
	status = {"fieldname": STATUS, "label": meta.get_label(STATUS)}

	if not frappe.db.exists("List View Settings", DOCTYPE):
		return  # the column order patch creates it; nothing to change here

	settings = frappe.get_doc("List View Settings", DOCTYPE)
	fields = json.loads(settings.fields or "[]")
	if any(f.get("fieldname") == STATUS for f in fields):
		return

	names = [f.get("fieldname") for f in fields]
	index = names.index(BEFORE) if BEFORE in names else len(fields)
	fields.insert(index, status)

	settings.fields = json.dumps(fields)
	settings.save(ignore_permissions=True)
	frappe.clear_cache(doctype=DOCTYPE)
