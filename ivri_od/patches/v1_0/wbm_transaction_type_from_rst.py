# Copyright (c) 2026, Profezzo and contributors
"""Weigh Bridge Measurement: Transaction Type (PURCHASE / SALE) fetched from its own RST Details.

Fills the new field on existing weighments from the linked RST, and adds the column right after
Status in the list. Other columns staff arranged in List View Settings are kept.
"""

import json

import frappe

DOCTYPE = "Weigh Bridge Measurement"
COLUMN = {"fieldname": "transaction_type", "label": "Transaction Type"}


def execute():
	frappe.reload_doc("procurement", "doctype", "weigh_bridge_measurement")
	frappe.db.sql(
		"""
		UPDATE `tabWeigh Bridge Measurement` wbm
		INNER JOIN `tabRST Details` rst ON rst.name = wbm.demo_rst_data
		SET wbm.transaction_type = rst.transaction_type
		WHERE IFNULL(wbm.transaction_type, '') != IFNULL(rst.transaction_type, '')
		"""
	)
	_add_list_column()
	frappe.clear_cache(doctype=DOCTYPE)


def _add_list_column():
	if not frappe.db.exists("List View Settings", DOCTYPE):
		return  # the default list (in_list_view fields) already shows the column
	settings = frappe.get_doc("List View Settings", DOCTYPE)
	columns = json.loads(settings.fields or "[]")
	if any(c.get("fieldname") == COLUMN["fieldname"] for c in columns):
		return
	after = next((i for i, c in enumerate(columns) if c.get("fieldname") == "tp_status"), len(columns) - 1)
	columns.insert(after + 1, COLUMN)
	settings.fields = json.dumps(columns)
	settings.save(ignore_permissions=True)
