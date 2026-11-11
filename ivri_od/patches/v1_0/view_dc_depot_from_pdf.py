# Copyright (c) 2026, Profezzo and contributors
"""DCRO View DC: the Depot Name column (table 2 of the DC PDF) on rows saved before it was added,
read from each row's saved PDF, as new reads do (portal_sync.add_dc_depot). Rows whose PDF is not
saved or cannot be read are left as they are. Record names and keys do not change."""

import json

import frappe

from ivri_od.procurement.portal_sync import DISTRICT_SECTIONS, add_dc_depot, build_row_hash


def execute():
	for site, section in DISTRICT_SECTIONS:
		for record in frappe.get_all(
			"Portal Record", filters={"site": site, "section": section}, fields=["name", "row_data"]
		):
			try:
				cells = json.loads(record.row_data or "{}") or {}
			except ValueError:
				continue
			fixed = add_dc_depot(site, section, cells, {}, record.name)
			if fixed != cells:
				frappe.db.set_value(
					"Portal Record",
					record.name,
					{"row_data": json.dumps(fixed, ensure_ascii=False), "row_hash": build_row_hash(fixed)},
					update_modified=False,
				)
