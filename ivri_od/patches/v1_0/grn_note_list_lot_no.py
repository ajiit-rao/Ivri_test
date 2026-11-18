# Copyright (c) 2026, Profezzo and contributors
"""GRN Note list: a Lot No column right after Depo Name (rice sent to a depo has a Lot No).

Only adds the column: other columns staff arranged in List View Settings are kept.
"""

import json

import frappe

DOCTYPE = "GRN Note"
COLUMN = {"fieldname": "lot_no", "label": "Lot No"}


def execute():
	frappe.reload_doc("procurement", "doctype", "grn_note")
	if frappe.db.exists("List View Settings", DOCTYPE):
		settings = frappe.get_doc("List View Settings", DOCTYPE)
		columns = json.loads(settings.fields or "[]")
		if not any(c.get("fieldname") == COLUMN["fieldname"] for c in columns):
			after = next(
				(i for i, c in enumerate(columns) if c.get("fieldname") == "depo_name"), len(columns) - 1
			)
			columns.insert(after + 1, COLUMN)
			settings.fields = json.dumps(columns)
			settings.save(ignore_permissions=True)
	frappe.clear_cache(doctype=DOCTYPE)
