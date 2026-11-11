# Copyright (c) 2026, Profezzo and contributors
# For license information, please see license.txt

"""Other TPs in one RST: a truck weighed under one Transit Pass that also carried paddy of other TPs.

Staff list the other TPs (TP No, PPC Name, Mill No, Qty) in the "Other TPs" table of the Weigh Bridge
Measurement, in the form or from the Mandi Book (Edit, click the RST No). On save:

- this weighment keeps the truck's weights; RST Net Weight is the whole truck, Net Weight is this TP's share;
- each other TP gets its own weighment ("Split from Weighment" = this one) with the same RST No, Quality
  Check, gate entry and vehicle, its weights in proportion and Net Weight = its Qty; its GRN Note is made
  the usual way;
- every GRN of the truck shows the other TPs of the truck in its own "Other TPs" table.

Example: RST 1201 weighs 250 QT net under TP 46 and carries 80 QT of TP 51.
Weighment TP 46: Net 170 (RST Net 250); new weighment TP 51: Net 80. GRN TP 46 = 170, GRN TP 51 = 80.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint, flt

from ivri_od.procurement.transit_pass_resolve import (
	get_transit_pass_for_ppc_and_tp_no,
	resolve_mill_master_name,
	resolve_ppc_master_name,
)

WBM = "Weigh Bridge Measurement"
ROW_FIELDS = ("transit_pass_no", "ppc_name", "mill_no", "qty", "pass_unique_key", "weighment")
# Copied from the truck's weighment to a split weighment: same RST, visit, Quality Check and vehicle.
COPY_FIELDS = (
	"rst_no", "date", "gate_entry", "quality_check", "slno_of_qc", "quality_test", "commodity", "gunny_type",
	"vehicle_no",
)
SPLIT_TP_STATUS = "TP Received"


def other_tp_total(rows) -> float:
	return flt(sum(flt(row.get("qty")) for row in rows or []), 3)


def _filled(rows):
	return [row for row in rows or [] if (row.get("transit_pass_no") or "").strip() or flt(row.get("qty"))]


# ------------------------------------------------------------------ weights


def adjust_weights_for_other_tps(wbm) -> None:
	"""End of Weigh Bridge Measurement._update_weights (every save and every Quality Check re-sync).

	Truck weighment: RST Net Weight = whole truck, Net Weight = that less the other TPs.
	Split weighment: its weights follow the truck's weighment, in proportion to its Qty.
	"""
	if (wbm.get("split_from_weighment") or "").strip():
		_copy_split_weights(wbm)
		return
	rst_net = flt(wbm.net_weight, 3)
	wbm.rst_net_weight = rst_net
	wbm.other_tp_qty = other_tp_total(_filled(wbm.get("other_tp_details")))
	wbm.net_weight = flt(max(rst_net - flt(wbm.other_tp_qty), 0.0), 3)


def _copy_split_weights(child) -> None:
	parent = frappe.db.get_value(
		WBM,
		child.split_from_weighment,
		["load_weight", "tare_weight", "gross_weight", "gunny_weight", "deduction", "net_weight", "rst_net_weight",
		 "total_bags", "no_of_bags", "quality_test"],
		as_dict=True,
	)
	if not parent:
		frappe.throw(_("Weighment {0} (Split from Weighment) not found.").format(child.split_from_weighment))
	rst_net = flt(parent.rst_net_weight) or flt(
		flt(parent.gross_weight) - flt(parent.gunny_weight) - flt(parent.deduction), 3
	)
	qty = flt(child.split_qty, 3)
	ratio = qty / rst_net if rst_net > 0 else 0.0
	child.rst_net_weight = flt(rst_net, 3)
	child.other_tp_qty = 0
	child.load_weight = flt(flt(parent.load_weight) * ratio, 3)
	child.tare_weight = flt(flt(parent.tare_weight) * ratio, 3)
	child.gross_weight = flt(flt(parent.gross_weight) * ratio, 3)
	child.gunny_weight = flt(flt(parent.gunny_weight) * ratio, 3)
	# Deduction makes gross - gunny - deduction exactly the Qty (no rounding left over).
	child.deduction = flt(child.gross_weight - child.gunny_weight - qty, 3)
	child.net_weight = 0 if (parent.quality_test or "") == "Rejected" else qty
	child.total_bags = int(round(cint(parent.total_bags) * ratio))
	child.no_of_bags = int(round(cint(parent.no_of_bags) * ratio))


# ------------------------------------------------------------------ validate


def validate_split_weighment(child) -> None:
	"""Weigh Bridge Measurement.validate of a split weighment: everything comes from the truck's weighment."""
	parent = frappe.get_doc(WBM, child.split_from_weighment)
	if parent.get("split_from_weighment"):
		frappe.throw(_("A split weighment cannot be split again."))
	for field in COPY_FIELDS:
		child.set(field, parent.get(field))
	child.is_farmer_or_agent = 0
	child.tp_status = SPLIT_TP_STATUS
	child.set("other_tp_details", [])
	child._validate_pass_unique_key()  # TP No, PPC, TP Weight, Truck No in TP of its own TP
	# Same truck as the truck's weighment, whatever the other TP says.
	from ivri_od.procurement.doctype.weigh_bridge_measurement.weigh_bridge_measurement import get_effective_truck_no

	truck = get_effective_truck_no(parent)
	child.same_truck_as_transit_pass = 1 if truck and truck != (child.truck_no_in_tp or "") else 0
	child.actual_truck_no = truck
	_copy_split_weights(child)


def validate_other_tps(wbm) -> None:
	"""Weigh Bridge Measurement.validate (last): check the Other TPs rows and find each TP."""
	rows = _filled(wbm.get("other_tp_details"))
	wbm.set("other_tp_details", rows)
	for idx, row in enumerate(rows, start=1):
		row.idx = idx
	wbm.other_tp_qty = other_tp_total(rows)
	if not rows:
		return
	if wbm.get("split_from_weighment"):
		frappe.throw(_("Add the other TPs on weighment {0}, the truck's own weighment.").format(wbm.split_from_weighment))
	if not (wbm.pass_unique_key or "").strip():
		frappe.throw(_("Other TPs can be added only to a weighment under a Transit Pass."))

	own_ppc = resolve_ppc_master_name(wbm.pacs_name) or ""
	season = frappe.db.get_value("PPAS Transit Pass", {"pass_unique_key": wbm.pass_unique_key}, "season") or None
	seen = set()
	for row in rows:
		row.transit_pass_no = (row.transit_pass_no or "").strip()
		if not row.transit_pass_no:
			frappe.throw(_("Other TPs, row {0}: enter the TP No.").format(row.idx))
		if flt(row.qty) <= 0:
			frappe.throw(_("Other TPs, row {0}: enter the Qty of TP No {1}.").format(row.idx, row.transit_pass_no))
		ppc = (row.ppc_name or "").strip() or own_ppc
		found = get_transit_pass_for_ppc_and_tp_no(ppc, row.transit_pass_no, season=season) if ppc else None
		key = ((found or {}).get("pass_unique_key") or (found or {}).get("name") or "").strip()
		if not key:
			frappe.throw(
				_("Other TPs, row {0}: TP No {1} not found in PPAS Transit Pass for PPC {2}{3}.").format(
					row.idx, row.transit_pass_no, ppc or "-", f", season {season}" if season else ""
				)
			)
		if key == (wbm.pass_unique_key or "").strip():
			frappe.throw(_("Other TPs, row {0}: TP No {1} is this weighment's own TP.").format(row.idx, row.transit_pass_no))
		if key in seen:
			frappe.throw(_("Other TPs: TP No {0} is added more than once.").format(row.transit_pass_no))
		seen.add(key)
		mill = resolve_mill_master_name(key, (found or {}).get("miller")) or ""
		if (row.mill_no or "").strip() and mill and row.mill_no.strip() != mill:
			frappe.throw(
				_("Other TPs, row {0}: TP No {1} is for Mill No {2}, not {3}.").format(row.idx, row.transit_pass_no, mill, row.mill_no)
			)
		row.ppc_name = ppc
		row.mill_no = (row.mill_no or "").strip() or mill or None
		row.pass_unique_key = key

	rst_net = flt(wbm.rst_net_weight, 3)
	if wbm.other_tp_qty >= rst_net:
		frappe.throw(
			_("The Qty of the other TPs ({0} QT) must be less than the Net Weight of this RST ({1} QT).").format(
				wbm.other_tp_qty, rst_net
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


# ------------------------------------------------------------------ split weighments


def sync_split_weighments(wbm) -> None:
	"""Weigh Bridge Measurement.on_update of the truck's weighment: one weighment per Other TPs row.

	New rows get a weighment, changed rows update theirs, removed rows lose theirs (and its GRN).
	Their GRN Notes are made and synced by the usual weighment save.
	"""
	if wbm.get("split_from_weighment"):
		return
	existing = set(frappe.get_all(WBM, filters={"split_from_weighment": wbm.name}, pluck="name"))
	if not existing and not wbm.get("other_tp_details"):
		return
	kept = set()
	for row in wbm.get("other_tp_details") or []:
		name = (row.weighment or "").strip()
		child = frappe.get_doc(WBM, name) if name in existing else frappe.new_doc(WBM)
		child.split_from_weighment = wbm.name
		child.split_qty = flt(row.qty, 3)
		child.pass_unique_key = row.pass_unique_key
		child.flags.ignore_permissions = True
		child.save()
		kept.add(child.name)
		if row.weighment != child.name:
			row.weighment = child.name
			frappe.db.set_value("Weighment Other TP", row.name, "weighment", child.name, update_modified=False)
	for name in existing - kept:
		_delete_split_weighment(name)


def _delete_split_weighment(name: str) -> None:
	# The truck's GRNs list it in their Other TPs: drop those rows first (the GRNs are synced again after).
	frappe.db.delete("Weighment Other TP", {"weighment": name, "parenttype": "GRN Note"})
	for grn in frappe.get_all("GRN Note", filters={"weigh_bridge_measurement": name, "docstatus": ["<", 2]}, pluck="name"):
		frappe.delete_doc("GRN Note", grn, ignore_permissions=True)
	frappe.delete_doc(WBM, name, ignore_permissions=True)


def resync_split_weighments(wbm_name: str) -> None:
	"""After a Quality Check re-sync wrote the truck's weights: the split weighments follow."""
	for name in frappe.get_all(WBM, filters={"split_from_weighment": wbm_name}, pluck="name"):
		child = frappe.get_doc(WBM, name)
		child.flags.ignore_permissions = True
		child.save()


# ------------------------------------------------------------------ GRN


def apply_other_tps_to_grn(grn, wbm_name: str, wbm_net_weight: float) -> None:
	"""GRN Note: Net Weight is the weighment's (this TP's share); "Other TPs" lists the rest of the truck."""
	w = frappe.db.get_value(WBM, wbm_name, ["split_from_weighment", "rst_net_weight", "pass_unique_key"], as_dict=True) or frappe._dict()
	truck = (w.split_from_weighment or "").strip() or wbm_name
	rows = frappe.get_all(
		"Weighment Other TP",
		filters={"parent": truck, "parenttype": WBM, "parentfield": "other_tp_details"},
		fields=list(ROW_FIELDS),
		order_by="idx asc",
	)
	if w.split_from_weighment:
		# A split GRN: the other TPs are the truck's own TP and the other split ones.
		p = frappe.db.get_value(WBM, truck, ["transit_pass_no", "pass_unique_key", "pacs_name", "net_weight"], as_dict=True)
		own = frappe._dict(
			transit_pass_no=p.transit_pass_no,
			ppc_name=resolve_ppc_master_name(p.pacs_name) or None,
			mill_no=resolve_mill_master_name(p.pass_unique_key, None) or None,
			qty=flt(p.net_weight, 3),
			pass_unique_key=p.pass_unique_key,
			weighment=truck,
		)
		# Not itself: by weighment, or by TP while a new split weighment is not linked to its row yet.
		rows = [own] + [
			row for row in rows
			if (row.weighment or "") != wbm_name and (row.pass_unique_key or "") != (w.pass_unique_key or "")
		]
	grn.set("other_tp_details", [])
	for row in rows:
		grn.append("other_tp_details", {field: row.get(field) for field in ROW_FIELDS})
	grn.other_tp_qty = other_tp_total(rows)
	grn.rst_net_weight = flt(w.rst_net_weight, 3) or flt(wbm_net_weight, 3)
	grn.net_weight = flt(wbm_net_weight, 3)


def _grn_for_wbm(wbm_name: str) -> str | None:
	return frappe.db.get_value("GRN Note", {"weigh_bridge_measurement": wbm_name, "docstatus": ["<", 2]}, "name")


# ------------------------------------------------------------------ Mandi Book dialog


@frappe.whitelist()
def get_other_tps(wbm_name: str) -> dict:
	"""Mandi Book dialog (click the RST No): the truck's weighment, its RST Net Weight and Other TPs."""
	wbm = frappe.get_doc(WBM, wbm_name)
	wbm.check_permission("read")
	if wbm.get("split_from_weighment"):
		wbm = frappe.get_doc(WBM, wbm.split_from_weighment)
	return {
		"wbm_name": wbm.name,
		"rst_no": (wbm.rst_no or wbm.name or "").strip(),
		"transit_pass_no": (wbm.transit_pass_no or "").strip(),
		"net_weight": flt(wbm.rst_net_weight, 3) or flt(wbm.net_weight, 3),
		"rows": [{field: row.get(field) for field in ROW_FIELDS} for row in wbm.get("other_tp_details") or []],
	}


@frappe.whitelist(methods=["POST"])
def save_other_tps(wbm_name: str, rows) -> dict:
	"""Mandi Book dialog: save the Other TPs of one RST; weighments and GRNs follow on save."""
	import json

	if isinstance(rows, str):
		rows = json.loads(rows or "[]")
	wbm = frappe.get_doc(WBM, wbm_name)
	wbm.check_permission("write")
	old = {(row.transit_pass_no or "").strip(): row.weighment for row in wbm.get("other_tp_details") or []}
	wbm.set("other_tp_details", [])
	for row in rows or []:
		values = {field: row.get(field) for field in ROW_FIELDS if field != "weighment"}
		# Keep the weighment of a TP already given, so it is updated and not made again.
		values["weighment"] = old.get((row.get("transit_pass_no") or "").strip())
		wbm.append("other_tp_details", values)
	wbm.save()
	grn = _grn_for_wbm(wbm.name)
	net = flt(frappe.db.get_value("GRN Note", grn, "net_weight"), 3) if grn else None
	return {
		"other_tp_qty": flt(wbm.other_tp_qty, 3),
		"grn": grn,
		"grn_net_weight": net,
		"count": cint(len(wbm.other_tp_details)),
		"weighments": [row.weighment for row in wbm.other_tp_details],
	}
