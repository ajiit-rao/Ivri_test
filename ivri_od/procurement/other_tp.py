# Copyright (c) 2026, Profezzo and contributors
# For license information, please see license.txt

"""Other TPs in one RST: a truck weighed under one Transit Pass that also carried paddy of other TPs.

Staff list the other TPs (TP No, PPC Name, Mill No, Qty) in the "Other TPs" table of the Weigh Bridge
Measurement, in the form or from the Mandi Book (Edit, click the RST No). On save:

- this weighment keeps the truck's weights; RST Net Weight is the whole truck, Net Weight is this TP's share;
- each other TP gets its own weighment ("Split from Weighment" = this one) with the same RST No, Quality
  Check, gate entry and vehicle, and the truck's Load and Tare Weight. Its Deduction starts at 0 and can be
  changed on that weighment; its Net Weight = its Qty less that Deduction. Its GRN Note is made the usual way;
- every weighment and GRN of the truck shows the other TPs of the truck in its own "Other TPs" table.

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
ROW_FIELDS = (
	"season", "transit_pass_no", "ppc_name", "mill_no", "qty", "gunny_weight", "deduction", "net_weight",
	"jute_bags", "plastic_bags", "pass_unique_key", "weighment",
)
# Copied from the truck's weighment to a split weighment: same RST, visit, Quality Check and vehicle.
COPY_FIELDS = (
	"rst_no", "date", "gate_entry", "quality_check", "slno_of_qc", "quality_test", "commodity", "gunny_type",
	"vehicle_no",
)
SPLIT_TP_STATUS = "TP Received"


def tp_season(pass_unique_key: str | None) -> str | None:
	"""Season Master of a Transit Pass (its PPAS season text, e.g. Kharif 2025 or K25)."""
	from ivri_od.procurement.doctype.season_master.season_master import resolve_season_master_name

	if not (pass_unique_key or "").strip():
		return None
	text = frappe.db.get_value("PPAS Transit Pass", {"pass_unique_key": pass_unique_key}, "season")
	return resolve_season_master_name(text) or None


def other_tp_total(rows) -> float:
	return flt(sum(flt(row.get("qty")) for row in rows or []), 3)


def row_net(row) -> float:
	"""Net Weight of an other TP: its Gross Weight (Qty) less its own Gunny Weight and Deduction."""
	return flt(flt(row.get("qty")) - flt(row.get("gunny_weight")) - flt(row.get("deduction")), 3)


def other_tp_sums(rows) -> frappe._dict:
	"""Totals of the other TPs: what the truck's own TP does not carry."""
	rows = rows or []
	return frappe._dict(
		qty=other_tp_total(rows),
		gunny=flt(sum(flt(r.get("gunny_weight")) for r in rows), 3),
		deduction=flt(sum(flt(r.get("deduction")) for r in rows), 3),
		net=flt(sum(row_net(r) for r in rows), 3),
		jute=sum(cint(r.get("jute_bags")) for r in rows),
		plastic=sum(cint(r.get("plastic_bags")) for r in rows),
	)


def bag_totals(bag_rows) -> tuple[int, int]:
	"""Jute and Plastic bags of a weighment's Bag Type table."""
	rows = bag_rows or []
	return sum(cint(r.get("jute_bags")) for r in rows), sum(cint(r.get("plastic_bags")) for r in rows)


def other_tp_bags_of_truck(wbm_name: str | None) -> tuple[int, int]:
	"""Bags given to the other TPs of a truck's own weighment (0, 0 for any other weighment).
	The truck's own TP has the truck's bags less these."""
	if not wbm_name or frappe.db.get_value(WBM, wbm_name, "split_from_weighment"):
		return 0, 0
	rows = frappe.get_all(
		"Weighment Other TP",
		filters={"parent": wbm_name, "parenttype": WBM, "parentfield": "other_tp_details"},
		fields=["jute_bags", "plastic_bags"],
	)
	return bag_totals(rows)


def _split_bags(child) -> tuple[int, int]:
	"""Bags of a split weighment: from its row in the truck's Other TPs (0, 0 when none given)."""
	given = child.flags.get("other_tp_bags")
	if given is not None:
		return cint(given[0]), cint(given[1])
	for filters in ({"weighment": child.name}, {"pass_unique_key": child.pass_unique_key}):
		if not (filters.get("weighment") or filters.get("pass_unique_key")):
			continue
		row = frappe.db.get_value(
			"Weighment Other TP",
			{"parent": child.split_from_weighment, "parenttype": WBM, "parentfield": "other_tp_details", **filters},
			["jute_bags", "plastic_bags"],
			as_dict=True,
		)
		if row:
			return cint(row.jute_bags), cint(row.plastic_bags)
	return 0, 0


def _filled(rows):
	return [row for row in rows or [] if (row.get("transit_pass_no") or "").strip() or flt(row.get("qty"))]


# ------------------------------------------------------------------ weights


def adjust_weights_for_other_tps(wbm) -> None:
	"""End of Weigh Bridge Measurement._update_weights (every save and every Quality Check re-sync).

	Truck weighment: RST Net Weight = whole truck, Net Weight = that less the other TPs.
	Split weighment: the truck's weights; Net Weight = its Qty less its own Deduction.
	"""
	if (wbm.get("split_from_weighment") or "").strip():
		_copy_split_weights(wbm)
		return
	rst_net = flt(wbm.net_weight, 3)
	wbm.rst_net_weight = rst_net
	sums = other_tp_sums(_filled(wbm.get("other_tp_details")))
	wbm.other_tp_qty = sums.qty
	# This TP's Qty: the truck's Gross Weight less the other TPs.
	wbm.tp_qty = flt(max(flt(wbm.gross_weight) - sums.qty, 0.0), 3)
	# This TP's Net: the RST Net less the other TPs' Net. Every other TP carries its own gunny and deduction,
	# this TP the rest of the truck's, so the Net of all TPs adds up to the RST Net Weight.
	wbm.net_weight = flt(max(rst_net - sums.net, 0.0), 3)


def _copy_split_weights(child) -> None:
	"""Split weighment: Load, Tare, Gross and bags are the truck's (the real weighbridge readings).

	Gunny Weight and Deduction are this TP's own (from its Other TPs row, 0 by default);
	Net Weight = Qty - Gunny Weight - Deduction.
	"""
	parent = frappe.db.get_value(
		WBM,
		child.split_from_weighment,
		["load_weight", "tare_weight", "gross_weight", "gunny_weight", "deduction", "rst_net_weight",
		 "total_bags", "no_of_bags", "quality_test"],
		as_dict=True,
	)
	if not parent:
		frappe.throw(_("Weighment {0} (Split from Weighment) not found.").format(child.split_from_weighment))
	rst_net = flt(parent.rst_net_weight) or flt(
		flt(parent.gross_weight) - flt(parent.gunny_weight) - flt(parent.deduction), 3
	)
	qty = flt(child.split_qty, 3)
	child.rst_net_weight = flt(rst_net, 3)
	for field in ("load_weight", "tare_weight", "gross_weight"):
		child.set(field, flt(parent.get(field), 3))
	child.no_of_bags = cint(parent.no_of_bags)
	deduction = flt(child.deduction, 3)
	gunny = flt(child.gunny_weight, 3)
	if deduction < 0 or gunny < 0:
		frappe.throw(_("Gunny Weight and Deduction cannot be less than 0."))
	if qty > 0 and gunny + deduction >= qty:
		frappe.throw(
			_("Gunny Weight + Deduction ({0} QT) must be less than the Gross Weight of this TP ({1} QT).").format(
				flt(gunny + deduction, 3), qty
			)
		)
	child.deduction = deduction
	child.gunny_weight = gunny
	child.net_weight = 0 if (parent.quality_test or "") == "Rejected" else flt(qty - gunny - deduction, 3)


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
	child._validate_pass_unique_key()  # TP No, PPC, TP Weight, Truck No in TP of its own TP
	# Same truck as the truck's weighment, whatever the other TP says.
	from ivri_od.procurement.doctype.weigh_bridge_measurement.weigh_bridge_measurement import get_effective_truck_no

	truck = get_effective_truck_no(parent)
	child.same_truck_as_transit_pass = 1 if truck and truck != (child.truck_no_in_tp or "") else 0
	child.actual_truck_no = truck
	_copy_split_weights(child)
	# Its bags: what its row in the truck's Other TPs gives it (Bag Type table, one row). Bag Condition stays 0:
	# the truck's own weighment keeps the Quality Check's Old / New bags.
	jute, plastic = _split_bags(child)
	child.set("bag_weight_details", [{"jute_bags": jute, "plastic_bags": plastic, "total_bags": jute + plastic, "gunny_weight_qt": 0}])
	child.set("old_new_bags", [{"old_bags": 0, "new_bags": 0}])
	child.total_bags = jute + plastic
	# Its "Other TPs": the truck's own TP and the other split TPs of the same RST.
	rows = truck_other_tps(child.name, child.split_from_weighment, child.pass_unique_key)
	child.set("other_tp_details", [{field: row.get(field) for field in ROW_FIELDS} for row in rows])
	child.other_tp_qty = other_tp_total(rows)
	# Gross Weight - other TPs = this TP's Qty (the truck's TP counts with its own Gross - Other TPs).
	child.tp_qty = flt(max(flt(child.gross_weight) - flt(child.other_tp_qty), 0.0), 3)


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
	own_season = tp_season(wbm.pass_unique_key)
	seen = set()
	for row in rows:
		row.transit_pass_no = (row.transit_pass_no or "").strip()
		if not row.transit_pass_no:
			frappe.throw(_("Other TPs, row {0}: enter the TP No.").format(row.idx))
		if flt(row.qty) <= 0:
			frappe.throw(_("Other TPs, row {0}: enter the Gross Weight of TP No {1}.").format(row.idx, row.transit_pass_no))
		row.gunny_weight = flt(row.gunny_weight, 3)
		row.deduction = flt(row.deduction, 3)
		if row.gunny_weight < 0 or row.deduction < 0:
			frappe.throw(_("Other TPs, row {0}: Gunny Weight and Deduction cannot be less than 0.").format(row.idx))
		if row.gunny_weight + row.deduction >= flt(row.qty):
			frappe.throw(
				_("Other TPs, row {0}: Gunny Weight + Deduction of TP No {1} must be less than its Gross Weight.").format(
					row.idx, row.transit_pass_no
				)
			)
		row.net_weight = row_net(row)
		row.jute_bags = cint(row.jute_bags)
		row.plastic_bags = cint(row.plastic_bags)
		if row.jute_bags < 0 or row.plastic_bags < 0:
			frappe.throw(_("Other TPs, row {0}: bags cannot be less than 0.").format(row.idx))
		ppc = (row.ppc_name or "").strip() or own_ppc
		# Season of the other TP: as chosen, else the season of this weighment's TP.
		season = (row.season or "").strip() or own_season
		if season and not frappe.db.exists("Season Master", season):
			frappe.throw(_("Other TPs, row {0}: Season {1} not found in Season Master.").format(row.idx, season))
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
		row.season = season or None
		row.mill_no = (row.mill_no or "").strip() or mill or None
		row.pass_unique_key = key

	sums = other_tp_sums(rows)
	# The truck's own TP keeps the rest of the truck's gunny and deduction, so the other TPs cannot take more.
	if sums.gunny > flt(wbm.gunny_weight, 3):
		frappe.throw(
			_("The Gunny Weight of the other TPs ({0} QT) is more than the truck's Gunny Weight ({1} QT).").format(
				sums.gunny, flt(wbm.gunny_weight, 3)
			)
		)
	if sums.deduction > flt(wbm.deduction, 3):
		frappe.throw(
			_("The Deduction of the other TPs ({0} QT) is more than the truck's Deduction ({1} QT).").format(
				sums.deduction, flt(wbm.deduction, 3)
			)
		)
	truck_jute, truck_plastic = bag_totals(wbm.get("bag_weight_details"))
	if sums.jute > truck_jute or sums.plastic > truck_plastic:
		frappe.throw(
			_("The other TPs have {0} Jute and {1} Plastic bags, but the truck has only {2} Jute and {3} Plastic bags.").format(
				sums.jute, sums.plastic, truck_jute, truck_plastic
			)
		)
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
		# Its own Gunny Weight and Deduction come from its row (RST Details, Mandi Book or this weighment).
		child.gunny_weight = flt(row.gunny_weight, 3)
		child.deduction = flt(row.deduction, 3)
		child.flags.other_tp_bags = (cint(row.jute_bags), cint(row.plastic_bags))
		child.flags.ignore_permissions = True
		child.save()
		kept.add(child.name)
		if row.weighment != child.name:
			row.weighment = child.name
			frappe.db.set_value("Weighment Other TP", row.name, "weighment", child.name, update_modified=False)
	for name in existing - kept:
		_delete_split_weighment(name)
	if len(kept) > 1:
		# Each split weighment lists the other split TPs: save again now that all are made and linked.
		for name in kept:
			child = frappe.get_doc(WBM, name)
			child.flags.ignore_permissions = True
			child.save()


def _delete_split_weighment(name: str) -> None:
	# The truck's GRNs and the other split weighments list it in their Other TPs: drop those rows first
	# (they are saved again after).
	frappe.db.delete("Weighment Other TP", {"weighment": name, "parent": ["!=", name]})
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


def truck_other_tps(wbm_name: str | None, truck: str, own_key: str | None) -> list:
	"""The Other TPs rows of the truck's weighment, as seen from one of its weighments.

	From the truck's own weighment: its rows. From a split weighment: the truck's own TP (Qty = Gross -
	Other TPs) and the other split TPs, not itself.
	"""
	rows = frappe.get_all(
		"Weighment Other TP",
		filters={"parent": truck, "parenttype": WBM, "parentfield": "other_tp_details"},
		fields=list(ROW_FIELDS),
		order_by="idx asc",
	)
	if not wbm_name or wbm_name == truck:
		return rows
	p = frappe.db.get_value(
		WBM, truck,
		["transit_pass_no", "pass_unique_key", "pacs_name", "gross_weight", "other_tp_qty", "gunny_weight", "deduction",
		 "net_weight"],
		as_dict=True,
	)
	if not p:
		return rows
	own = frappe._dict(
		season=tp_season(p.pass_unique_key),
		transit_pass_no=p.transit_pass_no,
		ppc_name=resolve_ppc_master_name(p.pacs_name) or None,
		mill_no=resolve_mill_master_name(p.pass_unique_key, None) or None,
		# Its Qty is Gross - Other TPs, so in every weighment of the RST: Gross - Other TPs = its own TP Qty.
		qty=flt(max(flt(p.gross_weight) - flt(p.other_tp_qty), 0.0), 3),
		gunny_weight=flt(max(flt(p.gunny_weight) - other_tp_sums(rows).gunny, 0.0), 3),
		deduction=flt(max(flt(p.deduction) - other_tp_sums(rows).deduction, 0.0), 3),
		net_weight=flt(p.net_weight, 3),
		jute_bags=max(_truck_bags(truck)[0] - other_tp_sums(rows).jute, 0),
		plastic_bags=max(_truck_bags(truck)[1] - other_tp_sums(rows).plastic, 0),
		pass_unique_key=p.pass_unique_key,
		weighment=truck,
	)
	# Not itself: by weighment, or by TP while a new split weighment is not linked to its row yet.
	return [own] + [
		row for row in rows
		if (row.weighment or "") != wbm_name and (row.pass_unique_key or "") != (own_key or "")
	]


def _truck_bags(wbm_name: str) -> tuple[int, int]:
	return bag_totals(
		frappe.get_all(
			"Weigh Bridge Bag Detail",
			filters={"parent": wbm_name, "parenttype": WBM, "parentfield": "bag_weight_details"},
			fields=["jute_bags", "plastic_bags"],
		)
	)


def apply_other_tps_to_grn(grn, wbm_name: str, wbm_net_weight: float) -> None:
	"""GRN Note: Net Weight is the weighment's (this TP's share); "Other TPs" lists the rest of the truck."""
	w = frappe.db.get_value(WBM, wbm_name, ["split_from_weighment", "rst_net_weight", "pass_unique_key"], as_dict=True) or frappe._dict()
	truck = (w.split_from_weighment or "").strip() or wbm_name
	rows = truck_other_tps(wbm_name if w.split_from_weighment else None, truck, w.pass_unique_key)
	grn.set("other_tp_details", [])
	for row in rows:
		grn.append("other_tp_details", {field: row.get(field) for field in ROW_FIELDS})
	grn.other_tp_qty = other_tp_total(rows)
	grn.rst_net_weight = flt(w.rst_net_weight, 3) or flt(wbm_net_weight, 3)
	grn.net_weight = flt(wbm_net_weight, 3)
	if not w.split_from_weighment and rows:
		# The truck's own TP: the truck's gunny and deduction less what the other TPs carry.
		sums = other_tp_sums(rows)
		grn.gunny_weight = flt(max(flt(grn.gunny_weight) - sums.gunny, 0.0), 3)
		grn.deduction = flt(max(flt(grn.deduction) - sums.deduction, 0.0), 3)


def _grn_for_wbm(wbm_name: str) -> str | None:
	return frappe.db.get_value("GRN Note", {"weigh_bridge_measurement": wbm_name, "docstatus": ["<", 2]}, "name")


# ------------------------------------------------------------------ Mandi Book dialog


def _all_tps(wbm) -> list[dict]:
	"""Every TP of the truck's RST: its own TP first, then the other TPs, with names and quantities."""
	gross = flt(wbm.gross_weight, 3)
	sums = other_tp_sums(_filled(wbm.get("other_tp_details")))
	own = {
		"season": tp_season(wbm.pass_unique_key),
		"transit_pass_no": (wbm.transit_pass_no or "").strip(),
		"ppc_name": resolve_ppc_master_name(wbm.pacs_name) or None,
		"mill_no": resolve_mill_master_name(wbm.pass_unique_key, None) or None,
		"qty": flt(wbm.get("tp_qty"), 3) or flt(max(gross - flt(wbm.other_tp_qty), 0.0), 3),
		"gunny_weight": flt(max(flt(wbm.gunny_weight) - sums.gunny, 0.0), 3),
		"deduction": flt(max(flt(wbm.deduction) - sums.deduction, 0.0), 3),
		"net_weight": flt(wbm.net_weight, 3),
		"jute_bags": max(bag_totals(wbm.get("bag_weight_details"))[0] - sums.jute, 0),
		"plastic_bags": max(bag_totals(wbm.get("bag_weight_details"))[1] - sums.plastic, 0),
		"weighment": wbm.name,
		"is_own": 1,
	}
	rows = [own] + [{field: row.get(field) for field in ROW_FIELDS} for row in wbm.get("other_tp_details") or []]
	for row in rows:
		if not row.get("is_own"):
			row["net_weight"] = row_net(row)
		row["grn"] = _grn_for_wbm(row["weighment"]) if row.get("weighment") else None
		ppc = row.get("ppc_name")
		row["ppc_label"] = (frappe.db.get_value("PPC Master", ppc, "ppc_name") if ppc else None) or ppc or ""
		mill = row.get("mill_no")
		m = frappe.db.get_value("Mill Master", mill, ["display_name", "company", "short_name"], as_dict=True) if mill else None
		row["mill_label"] = ((m.display_name or m.company or m.short_name) if m else None) or mill or ""
	return rows


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
		"season": tp_season(wbm.pass_unique_key),
		"net_weight": flt(wbm.rst_net_weight, 3) or flt(wbm.net_weight, 3),
		"gross_weight": flt(wbm.gross_weight, 3),
		"rows": [{field: row.get(field) for field in ROW_FIELDS} for row in wbm.get("other_tp_details") or []],
		"all_tps": _all_tps(wbm),
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


@frappe.whitelist(methods=["POST"])
def save_other_tp_bags(wbm_name: str, jute_bags=0, plastic_bags=0) -> dict:
	"""Mandi Book (Edit, click the bags of an other TP): the Jute / Plastic bags of that TP.

	Saved on its row in the truck's Other TPs; the truck's weighment save gives them to the TP's own
	weighment (Bag Type table) and GRN, and the truck's own TP keeps the rest."""
	split = frappe.db.get_value(WBM, wbm_name, ["split_from_weighment", "pass_unique_key"], as_dict=True)
	if not split or not split.split_from_weighment:
		frappe.throw(_("Bags can be given here only to an other TP of a truck. The truck's own TP keeps the rest."))
	truck = frappe.get_doc(WBM, split.split_from_weighment)
	truck.check_permission("write")
	rows = truck.get("other_tp_details") or []
	row = next((r for r in rows if r.weighment == wbm_name), None) or next(
		(r for r in rows if split.pass_unique_key and r.pass_unique_key == split.pass_unique_key), None
	)
	if not row:
		frappe.throw(_("TP of weighment {0} not found in the Other TPs of weighment {1}.").format(wbm_name, truck.name))
	row.jute_bags = cint(jute_bags)
	row.plastic_bags = cint(plastic_bags)
	truck.save()
	return {"truck": truck.name, "jute_bags": row.jute_bags, "plastic_bags": row.plastic_bags}


# ------------------------------------------------------------------ RST Details (both ways)

RST = "RST Details"
OTHER_TP_ROW = "Weighment Other TP"


def _row_key(row) -> tuple:
	"""What the user enters on an Other TPs row (links filled by the system are not compared)."""
	return (
		(row.get("transit_pass_no") or "").strip(),
		(row.get("ppc_name") or "").strip(),
		(row.get("season") or "").strip(),
		(row.get("mill_no") or "").strip(),
		flt(row.get("qty"), 3),
		flt(row.get("gunny_weight"), 3),
		flt(row.get("deduction"), 3),
		cint(row.get("jute_bags")),
		cint(row.get("plastic_bags")),
	)


def _rst_has_other_tps() -> bool:
	return frappe.get_meta(RST).has_field("other_tp_details")


def push_other_tps_from_rst(rst) -> bool:
	"""RST Details.on_update: the RST's Other TPs go to its weighment (truck's own weighment).

	The weighment save checks the rows and makes / updates / removes one weighment and GRN per other TP
	(see sync_split_weighments). The checked rows (PPC, Mill, Season, links) are copied back to the RST.
	Returns True when the weighment was changed.
	"""
	rows = _filled(rst.get("other_tp_details"))
	wbm_name = (rst.get("weigh_bridge_measurement") or "").strip()
	if not wbm_name or not frappe.db.exists(WBM, wbm_name):
		if rows:
			frappe.throw(
				_("Other TPs need the Weigh Bridge of RST {0}, but it has none. Correct the TP No / Party Name first.").format(
					rst.rst_no or rst.name
				)
			)
		return False
	wbm = frappe.get_doc(WBM, wbm_name)
	if wbm.get("split_from_weighment"):
		return False
	if [_row_key(r) for r in rows] == [_row_key(r) for r in _filled(wbm.get("other_tp_details"))]:
		return False

	old = {(row.transit_pass_no or "").strip(): row.weighment for row in wbm.get("other_tp_details") or []}
	wbm.set("other_tp_details", [])
	for row in rows:
		values = {field: row.get(field) for field in ROW_FIELDS if field != "weighment"}
		# Keep the weighment of a TP already given, so it is updated and not made again.
		values["weighment"] = old.get((row.get("transit_pass_no") or "").strip())
		wbm.append("other_tp_details", values)
	wbm.flags.from_rst = True
	wbm.flags.ignore_permissions = True
	wbm.save()
	copy_other_tps_to_rst(wbm)
	return True


def copy_other_tps_to_rst(wbm) -> None:
	"""The truck weighment's Other TPs are written to its RST Details (after a Mandi Book / weighment save).

	Written straight to the table (no RST save), so it does not start the RST -> weighment sync again.
	"""
	rst_name = (wbm.get("demo_rst_data") or "").strip()
	if not rst_name or wbm.get("split_from_weighment") or not _rst_has_other_tps():
		return
	if not frappe.db.exists(RST, rst_name):
		return
	if frappe.db.get_value(RST, rst_name, "weigh_bridge_measurement") != wbm.name:
		return
	rows = _filled(wbm.get("other_tp_details"))
	current = frappe.get_all(
		OTHER_TP_ROW,
		filters={"parenttype": RST, "parent": rst_name, "parentfield": "other_tp_details"},
		fields=list(ROW_FIELDS),
		order_by="idx asc",
	)
	if [{f: r.get(f) or None for f in ROW_FIELDS} for r in current] == [
		{f: (flt(r.get(f), 3) if f == "qty" else r.get(f)) or None for f in ROW_FIELDS} for r in rows
	]:
		return
	frappe.db.delete(OTHER_TP_ROW, {"parenttype": RST, "parent": rst_name, "parentfield": "other_tp_details"})
	for idx, row in enumerate(rows, start=1):
		frappe.get_doc(
			{
				"doctype": OTHER_TP_ROW,
				"parent": rst_name,
				"parenttype": RST,
				"parentfield": "other_tp_details",
				"idx": idx,
				**{field: row.get(field) for field in ROW_FIELDS},
			}
		).db_insert()
	frappe.db.set_value(RST, rst_name, "other_tp_qty", other_tp_total(rows), update_modified=False)
