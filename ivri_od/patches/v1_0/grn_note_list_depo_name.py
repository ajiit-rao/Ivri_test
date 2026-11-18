# Copyright (c) 2026, Profezzo and contributors
"""GRN Note list: a Depo Name column right after PPC, and Depo Name filled on existing depo GRNs.

A Rice Delivery to Depo GRN has no PPC; its Depo Name shows in the same place. Only adds the column:
other columns staff arranged in List View Settings are kept.
"""

import json

import frappe

DOCTYPE = "GRN Note"
COLUMN = {"fieldname": "depo_name", "label": "Depo Name"}


def execute():
	frappe.reload_doc("procurement", "doctype", "grn_note")
	_backfill_depo_name()
	_add_list_column()
	frappe.clear_cache(doctype=DOCTYPE)


def _backfill_depo_name():
	frappe.db.sql(
		"""
		UPDATE `tabGRN Note` g
		JOIN `tabDepo Master` d ON d.name = g.depo
		SET g.depo_name = d.depo_name
		WHERE IFNULL(g.depo, '') != '' AND IFNULL(g.depo_name, '') = ''
		"""
	)


def _add_list_column():
	if not frappe.db.exists("List View Settings", DOCTYPE):
		return  # the default list (in_list_view fields) is used; nothing saved to extend
	settings = frappe.get_doc("List View Settings", DOCTYPE)
	columns = json.loads(settings.fields or "[]")
	if any(c.get("fieldname") == COLUMN["fieldname"] for c in columns):
		return
	after = next((i for i, c in enumerate(columns) if c.get("fieldname") == "ppc"), len(columns) - 1)
	columns.insert(after + 1, COLUMN)
	settings.fields = json.dumps(columns)
	settings.save(ignore_permissions=True)
