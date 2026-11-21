# Copyright (c) 2026, Profezzo and contributors
# For license information, please see license.txt

"""Other TPs rows now carry their own Gunny Weight, Deduction and Net Weight, and RST Details shows them.

For each truck weighment with Other TPs:
- a row without Deduction takes the Deduction already given on its split weighment (Mandi Book dialog);
- the weighment is saved again, so the new rule applies (all TP nets add up to the RST Net Weight) and
  its split weighments and GRN Notes follow;
- the rows are copied to the RST Details.
"""

import frappe
from frappe.utils import flt

from ivri_od.procurement.other_tp import copy_other_tps_to_rst


def execute():
	frappe.reload_doc("procurement", "doctype", "weighment_other_tp")
	frappe.reload_doc("procurement", "doctype", "rst_details")
	parents = frappe.get_all(
		"Weighment Other TP",
		filters={"parenttype": "Weigh Bridge Measurement", "parentfield": "other_tp_details"},
		pluck="parent",
		distinct=True,
	)
	for name in parents:
		wbm = frappe.get_doc("Weigh Bridge Measurement", name)
		if wbm.get("split_from_weighment"):
			continue
		for row in wbm.other_tp_details:
			if not flt(row.deduction) and row.weighment:
				row.deduction = flt(frappe.db.get_value("Weigh Bridge Measurement", row.weighment, "deduction"), 3)
		frappe.db.savepoint("rst_other_tps")
		try:
			wbm.flags.ignore_permissions = True
			wbm.save()
		except Exception:
			frappe.db.rollback(save_point="rst_other_tps")
			frappe.log_error(
				message=frappe.get_traceback(),
				title=f"Patch rst_other_tps_from_weighment: {name} not saved, correct it by hand",
			)
			wbm.reload()
		copy_other_tps_to_rst(wbm)
