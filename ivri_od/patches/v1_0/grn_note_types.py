# Copyright (c) 2026, Profezzo and contributors
"""One GRN form for every weighment: GRN Note with a GRN Type.

GRN Type is Government Paddy, Rice Delivery to Depo or Private Deal. Rice and private GRN Notes take Mill
Name and Commodity from the weighment, and a private one also Purchase / Sale and the deal status.

1. Rice weighments: Depo Name filled; no Quality Check (rice is not tested).
2. Private deals (TP No empty / 0, party not a PPC and not a depo): RST and weighment status become
   "Local {Commodity} {Transaction Type}", e.g. "Local BRAN Sale".
3. Where the short-lived separate forms "Rice GRN" / "Private GRN" exist (one test site), their records are
   replaced by GRN Notes and the two forms are removed.
4. Every GRN Note is synced from its weighment, so GRN Type and the new fields are filled.

Safe to run more than once.
"""

import frappe

from ivri_od.procurement.doctype.rst_details.rst_details import (
	get_depo_for_party,
	is_private_procurement_rst,
	private_status_text,
)

OLD_FORMS = ("Rice GRN", "Private GRN")


def execute():
	for doctype in ("rst_details", "weigh_bridge_measurement", "grn_note"):
		frappe.reload_doc("procurement", "doctype", doctype)

	from ivri_od.procurement.doctype.weigh_bridge_measurement.weigh_bridge_measurement import (
		_ensure_grn_note_for_weigh_bridge,
		compute_wbm_tp_status,
		is_local_procurement_wbm,
	)

	_rice_weighments()
	_private_status(compute_wbm_tp_status, is_local_procurement_wbm)
	_replace_old_forms(_ensure_grn_note_for_weigh_bridge)
	_sync_all_grn_notes()


def _rice_weighments():
	for row in frappe.get_all(
		"Weigh Bridge Measurement", filters={"tp_status": "Rice Dispatch"}, fields=["name", "party_name"]
	):
		party = (row.party_name or "").strip()
		depo = get_depo_for_party(party)
		frappe.db.set_value(
			"Weigh Bridge Measurement",
			row.name,
			{
				"depo_name": (depo.get("depo_name") or "").strip() if depo else party,
				"quality_check": "",
				"quality_test": "",
				"slno_of_qc": 0,
			},
			update_modified=False,
		)
		frappe.db.delete("Weigh Bridge Bag Detail", {"parent": row.name, "parenttype": "Weigh Bridge Measurement"})


def _private_status(compute_wbm_tp_status, is_local_procurement_wbm):
	for rst in frappe.get_all(
		"RST Details", fields=["name", "tp_no", "party_name", "commodity", "transaction_type", "tp_status"]
	):
		if is_private_procurement_rst(rst):
			status = private_status_text(rst.commodity, rst.transaction_type)
			if status != rst.tp_status:
				frappe.db.set_value("RST Details", rst.name, "tp_status", status, update_modified=False)

	for name in frappe.get_all(
		"Weigh Bridge Measurement",
		filters={"is_farmer_or_agent": 1, "pass_unique_key": ["in", ["", None]]},
		pluck="name",
	):
		if is_local_procurement_wbm(name):
			status = compute_wbm_tp_status(frappe.get_doc("Weigh Bridge Measurement", name))
			frappe.db.set_value("Weigh Bridge Measurement", name, "tp_status", status, update_modified=False)


def _replace_old_forms(ensure_grn_note):
	for doctype in OLD_FORMS:
		if not frappe.db.table_exists(doctype):
			continue
		for row in frappe.db.sql(f"select name, weigh_bridge_measurement from `tab{doctype}`", as_dict=True):
			frappe.db.delete(doctype, {"name": row.name})
			if row.weigh_bridge_measurement and frappe.db.exists(
				"Weigh Bridge Measurement", row.weigh_bridge_measurement
			):
				try:
					ensure_grn_note(row.weigh_bridge_measurement)
				except Exception:
					frappe.log_error(
						message=frappe.get_traceback(),
						title=f"GRN Note for {row.weigh_bridge_measurement} (was {row.name}) failed",
					)
		if frappe.db.exists("DocType", doctype):
			frappe.delete_doc("DocType", doctype, ignore_permissions=True, force=True)
		frappe.db.sql_ddl(f"DROP TABLE IF EXISTS `tab{doctype}`")


def _sync_all_grn_notes():
	from ivri_od.procurement.doctype.grn_note.grn_note import sync_grn_from_weigh_bridge

	for grn in frappe.get_all(
		"GRN Note", filters={"docstatus": ["<", 2]}, fields=["name", "weigh_bridge_measurement"]
	):
		try:
			if grn.weigh_bridge_measurement and frappe.db.exists(
				"Weigh Bridge Measurement", grn.weigh_bridge_measurement
			):
				sync_grn_from_weigh_bridge(grn.weigh_bridge_measurement)
			else:
				doc = frappe.get_doc("GRN Note", grn.name)
				doc.sync_grn_type_and_trade_fields()
				frappe.db.set_value(
					"GRN Note",
					grn.name,
					{f: doc.get(f) for f in ("grn_type", "transaction_type", "deal_status")},
					update_modified=False,
				)
		except Exception:
			frappe.log_error(message=frappe.get_traceback(), title=f"GRN Type patch failed for {grn.name}")
