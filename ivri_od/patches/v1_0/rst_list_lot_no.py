# Copyright (c) 2026, Profezzo and contributors
"""RST Details list: a Lot No column right after TP No, and Lot No filled on existing depo RSTs.

For a depo RST (status Rice Dispatch) the TP No holds the Lot No. Only adds the column: other columns
staff arranged in List View Settings are kept.
"""

import json

import frappe

DOCTYPE = "RST Details"
COLUMN = {"fieldname": "lot_no", "label": "Lot No"}


def execute():
	frappe.reload_doc("procurement", "doctype", "rst_details")
	frappe.db.sql(
		"""
		UPDATE `tabRST Details`
		SET lot_no = TRIM(IFNULL(tp_no, ''))
		WHERE tp_status = 'Rice Dispatch'
		"""
	)
	_add_list_column()
	frappe.clear_cache(doctype=DOCTYPE)


def _add_list_column():
	if not frappe.db.exists("List View Settings", DOCTYPE):
		return  # the default list (in_list_view fields) already shows Lot No
	settings = frappe.get_doc("List View Settings", DOCTYPE)
	columns = json.loads(settings.fields or "[]")
	if any(c.get("fieldname") == COLUMN["fieldname"] for c in columns):
		return
	after = next((i for i, c in enumerate(columns) if c.get("fieldname") == "tp_no"), len(columns) - 1)
	columns.insert(after + 1, COLUMN)
	settings.fields = json.dumps(columns)
	settings.save(ignore_permissions=True)
