# Copyright (c) 2026, Profezzo and contributors
"""Quality Check list: fill the Unloading Point Name (the warehouse name) of the Quality Checks already saved.

New and edited Quality Checks fill it by themselves (fetched from the Warehouse on save). Safe to run again."""

import frappe


def execute():
	frappe.reload_doc("procurement", "doctype", "quality_check")
	for row in frappe.get_all("Quality Check", fields=["name", "unloading_point"]):
		name = (
			frappe.db.get_value("Warehouse", row.unloading_point, "warehouse_name")
			if row.unloading_point
			else ""
		)
		# db.set_value keeps the modified date and creates no version: this is only a display copy.
		frappe.db.set_value("Quality Check", row.name, "unloading_point_name", name or "", update_modified=False)
