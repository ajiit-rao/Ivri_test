# Copyright (c) 2026, Profezzo and contributors
"""Weigh Bridge Measurement: new Mill No / Mill Name, filled from its RST Mill No.

Runs before grn_note_types so rice and private GRN Notes copy the mill from the weighment.
"""

import frappe

from ivri_od.procurement.doctype.weigh_bridge_measurement.weigh_bridge_measurement import resolve_mill


def execute():
	frappe.reload_doc("procurement", "doctype", "weigh_bridge_measurement")
	rows = frappe.db.sql(
		"""
		SELECT wbm.name, rst.mill_name
		FROM `tabWeigh Bridge Measurement` wbm
		INNER JOIN `tabRST Details` rst ON rst.name = wbm.demo_rst_data
		WHERE IFNULL(rst.mill_name, '') != ''
		""",
		as_dict=True,
	)
	cache = {}
	for row in rows:
		given = row.mill_name.strip()
		if given not in cache:
			cache[given] = resolve_mill(given)
		mill, mill_name = cache[given]
		frappe.db.set_value(
			"Weigh Bridge Measurement", row.name, {"mill": mill, "mill_name": mill_name}, update_modified=False
		)
