"""Fill Bag Type (Jute / Plastic) and Bag Condition (Old / New) of every weighment, then copy them to its GRN Note.

Rule for both tables: Quality Check accepted -> QC lines; else RST bags; else one row with 0.
Rows are written directly (no save hooks), so no other value changes.
"""

import frappe

from ivri_od.procurement.doctype.grn_note.grn_note import _wbm_bag_counts_from_child_table

TABLES = ("bag_weight_details", "old_new_bags")


def _counts(doc, fieldname):
	return [tuple(sorted((k, v) for k, v in r.as_dict().items() if k.endswith("_bags"))) for r in doc.get(fieldname)]


def execute():
	for doctype in ("weigh_bridge_bag_detail", "quality_check_old_new_bag_detail", "weigh_bridge_measurement", "grn_note", "rst_details"):
		frappe.reload_doc("procurement", "doctype", doctype)

	for name in frappe.get_all("Weigh Bridge Measurement", pluck="name"):
		doc = frappe.get_doc("Weigh Bridge Measurement", name)
		before = {t: _counts(doc, t) for t in TABLES}
		doc._sync_bag_details_from_qc()
		for t in TABLES:
			if _counts(doc, t) != before[t]:
				doc.update_child_table(t)
		frappe.db.set_value("Weigh Bridge Measurement", name, "total_bags", doc.total_bags, update_modified=False)

	for name in frappe.get_all(
		"GRN Note", filters={"weigh_bridge_measurement": ["is", "set"], "docstatus": ["<", 2]}, pluck="name"
	):
		grn = frappe.get_doc("GRN Note", name)
		jute, plastic, total = _wbm_bag_counts_from_child_table(grn.weigh_bridge_measurement)
		frappe.db.set_value(
			"GRN Note", name, {"jute_bags": jute, "plastic_bags": plastic, "total_bags": total}, update_modified=False
		)
		grn._apply_wbm_bag_condition(grn.weigh_bridge_measurement)
		grn.update_child_table("old_new_bags")

	# RST Total Bags is now Jute + Plastic only
	frappe.db.sql("update `tabRST Details` set total_bags = ifnull(jute_bags, 0) + ifnull(plastic_bags, 0)")
