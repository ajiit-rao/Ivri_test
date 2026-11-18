# Copyright (c) 2026, Profezzo and contributors
"""Quality Check list: fill the Type of Bags summary of the Quality Checks already saved.

New and edited Quality Checks fill it by themselves (on save). Safe to run again."""

import frappe
from frappe import _
from frappe.utils import cint


def execute():
	frappe.reload_doc("procurement", "doctype", "quality_check")
	for name in frappe.get_all("Quality Check", pluck="name"):
		rows = frappe.get_all(
			"Quality Check Bag Detail",
			filters={"parent": name, "parenttype": "Quality Check", "parentfield": "type_of_pkt"},
			fields=["jute_pkt_no", "no_of_plastic_bag"],
		)
		filled = [r for r in rows if cint(r.jute_pkt_no) or cint(r.no_of_plastic_bag)]
		summary = ""
		if len(filled) == 1:
			summary = _("Jute {0}, Plastic {1}").format(cint(filled[0].jute_pkt_no), cint(filled[0].no_of_plastic_bag))
		# db.set_value keeps the modified date and creates no version: this is only a display copy.
		frappe.db.set_value("Quality Check", name, "type_of_pkt_summary", summary, update_modified=False)
