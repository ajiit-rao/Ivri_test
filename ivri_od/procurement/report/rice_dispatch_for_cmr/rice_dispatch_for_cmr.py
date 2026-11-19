# Copyright (c) 2026, Profezzo and contributors

"""Rice Dispatch for CMR: every rice dispatch to a depot, with its weighment and what the
government portals show for the same lot.

Rows: Weigh Bridge Measurement with Status "Rice Dispatch" (made from an RST whose Party Name is
a Depo Master Depo Name). Depot Code = that Depo Master.

Portal row of the lot (saved by Portal Data Extraction as Portal Record), found by Depot Code +
Lot No:
- RRC depot: SCMS "Transit Challan RRC" (challan and its PDF) and SCMS "Lot Search" (AC Note
  and its PDF).
- FCI / SWC depot: DCRO "DC Transit Challan" (the Details PDF is the transit challan; the
  AC Note Doc PDF the AC Note).
Only rows of the weighment's mill (portal Miller Code = Mill Master code) are used.
One lot can go in several trucks (one challan each): then the row with the weighment's vehicle
number is taken. The Match column says how the row was found.
Weights are in quintals (QT), as stored; nothing is converted.
"""

from __future__ import annotations

import json
import re
from datetime import datetime

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate

RICE_DISPATCH_STATUS = "Rice Dispatch"

SCMS, DCRO = "SCMS", "DCRO"
SCMS_CHALLAN = "Transit Challan RRC"
SCMS_LOT_SEARCH = "Lot Search"
DCRO_CHALLAN = "DC Transit Challan"
DCRO_CHALLAN_DOC = "Details"
DCRO_AC_NOTE_DOC = "AC Note Doc"

MATCH_VEHICLE = "Lot + Vehicle"
MATCH_LOT = "Lot only"
MATCH_NONE = "Not found"

# Columns added up in the total row.
TOTAL_FIELDS = ("bags", "gross_weight", "tare_weight", "net_weight", "portal_bags", "accepted_qty", "difference")


def execute(filters=None):
	filters = frappe._dict(filters or {})
	data = get_data(filters)
	if data:
		data.append(total_row(data))
	return get_columns(), data


def get_columns():
	def col(fieldname, label, fieldtype="Data", width=110, **extra):
		return {"fieldname": fieldname, "label": _(label), "fieldtype": fieldtype, "width": width, **extra}

	def qt(fieldname, label, width=110):
		return col(fieldname, label, "Float", width, precision=3)

	return [
		# Weighment
		col("weighment_date", "Weighment Date", "Datetime", 150),
		col("rst_no", "RST No", width=80),
		col("weighment", "Weighment", "Link", 140, options="Weigh Bridge Measurement"),
		col("mill_name", "Mill Name", width=220),
		col("depot_name", "Depot Name", width=170),
		col("depot_code", "Depot Code", "Link", 100, options="Depo Master"),
		col("lot_no", "Lot No", width=70),
		col("commodity", "Commodity", width=170),
		col("vehicle_no", "Vehicle No", width=110),
		col("bags", "Bags", "Int", 70),
		qt("gross_weight", "Gross Weight (QT)"),
		qt("tare_weight", "Tare Weight (QT)"),
		qt("net_weight", "Net Weight (QT)"),
		# Portal (SCMS / DCRO)
		col("portal", "Portal", width=70),
		col("match", "Match", width=100),
		col("dc_no", "DC No", width=110),
		col("challan_no", "Challan / Contract No", width=150),
		col("challan_date", "Challan Date", width=100),
		col("portal_vehicle_no", "Portal Vehicle No", width=120),
		col("portal_bags", "Portal Bags", "Int", 90),
		col("ac_note_no", "AC Note No", width=90),
		col("accepted_date", "Accepted Date", width=105),
		qt("accepted_qty", "Accepted Qty (QT)", 130),
		qt("difference", "Difference (QT)"),
		col("moisture", "Moisture %", "Float", 90, precision=2),
		col("portal_status", "Portal Status", width=110),
		# Documents
		col("transit_challan_file", "Transit Challan", width=120),
		col("ac_note_file", "AC Note", width=100),
	]


# ---------------------------------------------------------------- weighments


def _name_key(name) -> str:
	"""Case and extra spaces do not matter, as in the RST depot match."""
	return " ".join((name or "").split()).casefold()


def _depos() -> dict[str, dict]:
	"""Depo Master code, Depo Name and Depo Type by lower-case Depo Name, oldest record first."""
	depos: dict[str, dict] = {}
	for row in frappe.get_all(
		"Depo Master", fields=["name", "depo_name", "depo_type"], order_by="creation asc"
	):
		depos.setdefault(
			_name_key(row.depo_name),
			{"code": row.name, "depo_name": " ".join((row.depo_name or "").split()), "type": row.depo_type},
		)
	return depos


def _depot_filter_key(depot) -> str:
	"""The Depot Name filter is a Depo Master (its code) or a typed depot name."""
	depot = (depot or "").strip()
	if not depot:
		return ""
	if frappe.db.exists("Depo Master", depot):
		depot = frappe.db.get_value("Depo Master", depot, "depo_name") or depot
	return _name_key(depot)


def _weighments(filters) -> list[dict]:
	conditions = [["tp_status", "=", RICE_DISPATCH_STATUS], ["docstatus", "<", 2]]
	if filters.get("from_date"):
		conditions.append(["date", ">=", getdate(filters.from_date)])
	if filters.get("to_date"):
		conditions.append(["date", "<", frappe.utils.add_days(getdate(filters.to_date), 1)])
	if filters.get("mill"):
		conditions.append(["mill", "=", filters.mill])
	return frappe.get_all(
		"Weigh Bridge Measurement",
		filters=conditions,
		fields=[
			"name",
			"date",
			"rst_no",
			"mill",
			"mill_name",
			"party_name",
			"depo_name",
			"lot_no",
			"commodity",
			"actual_truck_no",
			"vehicle_no",
			"total_bags",
			"gross_weight",
			"tare_weight",
			"net_weight",
		],
		order_by="date asc, name asc",
	)


# ---------------------------------------------------------------- portal rows


def _key(text) -> str:
	"""Letters and digits only, lower case: "Lot No." and "Lot No" are the same column."""
	return re.sub(r"[^a-z0-9]", "", (text or "").lower())


def _cell(cells: dict, *headers) -> str:
	"""First filled cell of these column headers (spelling of spaces / dots does not matter)."""
	by_key = {_key(h): v for h, v in cells.items()}
	for header in headers:
		value = (by_key.get(_key(header)) or "").strip()
		if value:
			return value
	return ""


def lot_key(lot) -> str:
	"""Lot "061" and "61" are the same lot."""
	lot = (lot or "").strip()
	return lot.lstrip("0") or lot


def vehicle_key(vehicle) -> str:
	return re.sub(r"[^A-Z0-9]", "", (vehicle or "").upper())


def depot_code_of(text) -> str:
	"""Depot code of a portal cell: "DG051601" or "DG051601-RMC,Kantabanji" -> "DG051601"."""
	return (text or "").split("-")[0].strip().upper()


def _portal_date(text):
	"""Portal dates are dd/mm/yyyy or dd-mm-yyyy; unknown dates sort first."""
	for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
		try:
			return datetime.strptime((text or "").strip(), fmt)
		except ValueError:
			continue
	return datetime.min


def _num(text, precision=3):
	"""Number of a portal cell ("289.03600", "1,234.5"); None when empty or not a number."""
	try:
		return round(float((text or "").replace(",", "").strip()), precision)
	except ValueError:
		return None


def _load(raw) -> dict:
	try:
		value = json.loads(raw or "{}")
	except (TypeError, ValueError):
		return {}
	return value if isinstance(value, dict) else {}


def _portal_index(site: str, section: str, depot_headers, lot_headers) -> dict[tuple, list[dict]]:
	"""Rows of one portal section by (depot code, lot)."""
	index: dict[tuple, list[dict]] = {}
	for record in frappe.get_all(
		"Portal Record",
		filters={"site": site, "section": section},
		fields=["name", "row_data", "receipt_file", "documents", "mill_id"],
	):
		cells = _load(record.row_data)
		depot = depot_code_of(_cell(cells, *depot_headers))
		lot = lot_key(_cell(cells, *lot_headers))
		if not (depot and lot):
			continue
		index.setdefault((depot, lot), []).append(
			{
				"cells": cells,
				"receipt": record.receipt_file or "",
				"documents": _load(record.documents),
				# Miller Code of the row (e.g. M051007), else the mill the agent saved it under.
				"mill": (_cell(cells, "Miller Code", "MillerCode") or record.mill_id or "").strip().upper(),
			}
		)
	return index


def of_mill(candidates: list[dict], mill: str) -> list[dict]:
	"""Rows of this mill: a row of another mill is never taken (rows without a mill are kept).
	No mill on the weighment: all rows."""
	mill = (mill or "").strip().upper()
	if not mill:
		return candidates
	return [c for c in candidates if not c.get("mill") or c["mill"] == mill]


def pick_row(candidates: list[dict], vehicle: str, vehicle_headers, date_headers) -> tuple[dict | None, str]:
	"""The portal row of this weighment among the rows of its lot: the one with the same vehicle,
	else the newest. Returns (row, how it matched)."""
	if not candidates:
		return None, MATCH_NONE
	wanted = vehicle_key(vehicle)
	same_vehicle = [c for c in candidates if wanted and vehicle_key(_cell(c["cells"], *vehicle_headers)) == wanted]
	pool, how = (same_vehicle, MATCH_VEHICLE) if same_vehicle else (candidates, MATCH_LOT)
	newest = max(pool, key=lambda c: _portal_date(_cell(c["cells"], *date_headers)))
	return newest, how


class PortalLookup:
	"""Loads the three portal sections once per report run."""

	def __init__(self):
		self.scms_challans = _portal_index(SCMS, SCMS_CHALLAN, ["Depot Code"], ["Lot No"])
		self.scms_lots = _portal_index(SCMS, SCMS_LOT_SEARCH, ["Depot"], ["Lot No."])
		self.dcro_challans = _portal_index(DCRO, DCRO_CHALLAN, ["Depot Code"], ["Lot No."])

	def find(self, depot_code: str, lot: str, vehicle: str, mill: str = "") -> dict:
		key = (depot_code_of(depot_code), lot_key(lot))
		if not all(key):
			return {"match": MATCH_NONE}
		dcro = of_mill(self.dcro_challans.get(key, []), mill)
		if dcro:
			return self._dcro(*pick_row(dcro, vehicle, ["Vechicle No.", "Vehicle No."], ["Accepted Date"]))
		challans = of_mill(self.scms_challans.get(key, []), mill)
		lots = of_mill(self.scms_lots.get(key, []), mill)
		if challans or lots:
			return self._scms(challans, lots, vehicle)
		return {"match": MATCH_NONE}

	def _dcro(self, row, how) -> dict:
		cells, docs = row["cells"], row["documents"]
		return {
			"portal": DCRO,
			"match": how,
			"dc_no": _cell(cells, "DC Order No"),
			"challan_no": _cell(cells, "Contract No."),
			"challan_date": "",
			"portal_vehicle_no": _cell(cells, "Vechicle No.", "Vehicle No."),
			"portal_bags": cint(_num(_cell(cells, "No. of Bags(In kg.)", "No. of Bags"))),
			"ac_note_no": _cell(cells, "Acceptance Note No"),
			"accepted_date": _cell(cells, "Accepted Date"),
			"accepted_qty": _num(_cell(cells, "Net Weight")),
			"moisture": _num(_cell(cells, "Moisture"), 2),
			"portal_status": _cell(cells, "Pending At"),
			"transit_challan_file": docs.get(DCRO_CHALLAN_DOC) or "",
			"ac_note_file": docs.get(DCRO_AC_NOTE_DOC) or "",
		}

	def _scms(self, challans, lots, vehicle) -> dict:
		challan, how = pick_row(challans, vehicle, ["Vehicle No"], ["Challan Date"])
		# Lot Search: the lot's AC Note; the same DC as the challan when there is one.
		if challan and _cell(challan["cells"], "DC No"):
			same_dc = [r for r in lots if _cell(r["cells"], "DC No.") == _cell(challan["cells"], "DC No")]
			lots = same_dc or lots
		lot, lot_how = pick_row(lots, vehicle, ["Vehicle No"], ["Receipt Date"])
		c = challan["cells"] if challan else {}
		lc = lot["cells"] if lot else {}
		qty = _cell(lc, "Qty(In Qtl.)", "Qty")
		return {
			"portal": SCMS,
			"match": how if challan else lot_how,
			"dc_no": _cell(c, "DC No") or _cell(lc, "DC No."),
			"challan_no": _cell(c, "Challan No."),
			"challan_date": _cell(c, "Challan Date") or _cell(lc, "Transit Challan Date"),
			"portal_vehicle_no": _cell(c, "Vehicle No") or _cell(lc, "Vehicle No"),
			"portal_bags": cint(_num(_cell(c, "Bag") or _cell(lc, "No.of Bag"))),
			"ac_note_no": _cell(lc, "A.C. Note No."),
			"accepted_date": _cell(lc, "Receipt Date"),
			"accepted_qty": _num(qty),
			"moisture": None,
			"portal_status": _cell(c, "Lot Challan Receipt status") or _cell(lc, "Challan Status"),
			"transit_challan_file": challan["receipt"] if challan else "",
			"ac_note_file": lot["receipt"] if lot else "",
		}


# ---------------------------------------------------------------- report rows


def get_data(filters):
	filters = frappe._dict(filters or {})
	if filters.get("from_date") and filters.get("to_date") and getdate(filters.from_date) > getdate(filters.to_date):
		frappe.throw(_("From Date cannot be after To Date."))

	depos = _depos()
	wanted = _depot_filter_key(filters.get("depot_name"))
	lookup = PortalLookup()

	rows = []
	for w in _weighments(filters):
		party = " ".join((w.depo_name or w.party_name or "").split())
		if wanted and _name_key(party) != wanted:
			continue
		depo = depos.get(_name_key(party)) or {}
		vehicle = (w.actual_truck_no or w.vehicle_no or "").strip()
		row = {
			"weighment_date": w.date,
			"rst_no": w.rst_no,
			"weighment": w.name,
			# RST Mill No -> weighment (Mill Master) -> GRN: the same mill everywhere.
			"mill_name": w.mill_name or "",
			"depot_name": depo.get("depo_name") or party,
			"depot_code": depo.get("code") or "",
			"lot_no": (w.lot_no or "").strip(),
			"commodity": w.commodity,
			"vehicle_no": vehicle,
			"bags": cint(w.total_bags),
			"gross_weight": flt(w.gross_weight, 3),
			"tare_weight": flt(w.tare_weight, 3),
			"net_weight": flt(w.net_weight, 3),
		}
		row.update(lookup.find(row["depot_code"], row["lot_no"], vehicle, w.mill))
		if row.get("accepted_qty") is not None:
			# Shortage (negative) or excess at the depot against our weighment.
			row["difference"] = flt(row["accepted_qty"] - row["net_weight"], 3)
		if filters.get("portal_status") == "Found" and row["match"] == MATCH_NONE:
			continue
		if filters.get("portal_status") == "Not Found" and row["match"] != MATCH_NONE:
			continue
		rows.append(row)
	return rows


def total_row(rows):
	total = {"depot_name": _("Total ({0} dispatches)").format(len(rows)), "is_total": 1}
	for field in TOTAL_FIELDS:
		total[field] = flt(sum(flt(r.get(field)) for r in rows), 3)
	return total
