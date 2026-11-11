# Copyright (c) 2026, Profezzo and contributors
# For license information, please see license.txt

"""Other TPs in one RST: a truck weighed under one Transit Pass that also carried paddy of other TPs.

Staff list the other TPs (TP No, PPC Name, Mill No, Qty) on the Weigh Bridge Measurement, in the
form or from the Mandi Book (Edit, click the TP No). The weighment keeps the Net Weight of the whole
truck; the GRN Note gets the same rows and its Net Weight is the truck's Net Weight less their Qty.

Example: RST 1201 weighs 250 QT net under TP 46 and carries 80 QT of TP 51. GRN Net Weight = 170 QT.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint, flt

ROW_FIELDS = ("transit_pass_no", "ppc_name", "mill_no", "qty")


def other_tp_total(rows) -> float:
	return flt(sum(flt(row.get("qty")) for row in rows or []), 3)


def validate_other_tps(wbm) -> None:
	"""Weigh Bridge Measurement.validate: clean the rows, check them and set Other TP Qty."""
	rows = [row for row in wbm.get("other_tp_details") or [] if (row.transit_pass_no or "").strip() or flt(row.qty)]
	wbm.set("other_tp_details", rows)
	for idx, row in enumerate(rows, start=1):
		row.idx = idx
	wbm.other_tp_qty = other_tp_total(rows)
	if not rows:
		return

	if not (wbm.pass_unique_key or "").strip():
		frappe.throw(_("Other TPs can be added only to a weighment under a Transit Pass."))

	own_tp = (wbm.transit_pass_no or "").strip()
	seen = set()
	for row in rows:
		row.transit_pass_no = (row.transit_pass_no or "").strip()
		if not row.transit_pass_no:
			frappe.throw(_("Other TPs, row {0}: enter the TP No.").format(row.idx))
		if flt(row.qty) <= 0:
			frappe.throw(_("Other TPs, row {0}: enter the Qty of TP No {1}.").format(row.idx, row.transit_pass_no))
		if own_tp and row.transit_pass_no == own_tp:
			frappe.throw(_("Other TPs, row {0}: TP No {1} is this weighment's own TP.").format(row.idx, own_tp))
		mark = (row.transit_pass_no, (row.ppc_name or "").strip(), (row.mill_no or "").strip())
		if mark in seen:
			frappe.throw(_("Other TPs: TP No {0} is added more than once.").format(row.transit_pass_no))
		seen.add(mark)

	net = flt(wbm.net_weight, 3)
	if wbm.other_tp_qty >= net:
		frappe.throw(
			_("The Qty of the other TPs ({0} QT) must be less than the Net Weight of this RST ({1} QT).").format(
				wbm.other_tp_qty, net
			)
		)

	grn = _grn_for_wbm(wbm.name) if not wbm.is_new() else None
	if grn and frappe.db.exists("Mandi Book TP Split", {"grn_note": grn}):
		frappe.throw(
			_(
				"RST {0} is already split over several TP Nos in the Mandi Book (RST No, attach TP No). "
				"Use 'Back to one TP No' there first, then add the other TPs here."
			).format(wbm.rst_no or wbm.name)
		)


def apply_other_tps_to_grn(grn, wbm_name: str, rst_net_weight: float) -> None:
	"""GRN Note: copy the weighment's other TPs; Net Weight = RST Net Weight - Other TP Qty."""
	rows = frappe.get_all(
		"Weighment Other TP",
		filters={"parent": wbm_name, "parenttype": "Weigh Bridge Measurement", "parentfield": "other_tp_details"},
		fields=list(ROW_FIELDS),
		order_by="idx asc",
	)
	grn.set("other_tp_details", [])
	for row in rows:
		grn.append("other_tp_details", {field: row.get(field) for field in ROW_FIELDS})
	grn.rst_net_weight = flt(rst_net_weight, 3)
	grn.other_tp_qty = other_tp_total(rows)
	grn.net_weight = flt(max(grn.rst_net_weight - grn.other_tp_qty, 0.0), 3)


def _grn_for_wbm(wbm_name: str) -> str | None:
	return frappe.db.get_value("GRN Note", {"weigh_bridge_measurement": wbm_name, "docstatus": ["<", 2]}, "name")


@frappe.whitelist()
def get_other_tps(pass_unique_key: str) -> dict:
	"""Mandi Book dialog: the RSTs of this TP, each with its Net Weight and the other TPs given so far."""
	frappe.has_permission("Weigh Bridge Measurement", "read", throw=True)
	key = (pass_unique_key or "").strip()
	grns = frappe.get_all(
		"GRN Note",
		filters={"pass_unique_key": key, "is_local_procurement": 0, "docstatus": ["<", 2], "weigh_bridge_measurement": ["is", "set"]},
		fields=["name", "rst_no", "weigh_bridge_measurement", "transit_pass_no"],
		order_by="receipt_datetime asc, creation asc",
	)
	rsts = []
	for grn in grns:
		wbm = frappe.get_doc("Weigh Bridge Measurement", grn.weigh_bridge_measurement)
		rsts.append(
			{
				"wbm": wbm.name,
				"grn": grn.name,
				"rst_no": (grn.rst_no or wbm.rst_no or wbm.name).strip(),
				"net_weight": flt(wbm.net_weight, 3),
				"is_split": bool(frappe.db.exists("Mandi Book TP Split", {"grn_note": grn.name})),
				"rows": [{field: row.get(field) for field in ROW_FIELDS} for row in wbm.get("other_tp_details") or []],
			}
		)
	tp_no = grns[0].transit_pass_no if grns else frappe.db.get_value("PPAS Transit Pass", key, "transit_pass_no")
	return {"transit_pass_no": tp_no or "", "rsts": rsts}


@frappe.whitelist(methods=["POST"])
def save_other_tps(wbm_name: str, rows) -> dict:
	"""Mandi Book dialog: save the other TPs of one RST on its weighment; the GRN follows on save."""
	import json

	if isinstance(rows, str):
		rows = json.loads(rows or "[]")
	wbm = frappe.get_doc("Weigh Bridge Measurement", wbm_name)
	wbm.check_permission("write")
	wbm.set("other_tp_details", [])
	for row in rows or []:
		wbm.append("other_tp_details", {field: row.get(field) for field in ROW_FIELDS})
	wbm.save()
	grn = _grn_for_wbm(wbm.name)
	net = flt(frappe.db.get_value("GRN Note", grn, "net_weight"), 3) if grn else None
	return {"other_tp_qty": flt(wbm.other_tp_qty, 3), "grn": grn, "grn_net_weight": net, "count": cint(len(wbm.other_tp_details))}
