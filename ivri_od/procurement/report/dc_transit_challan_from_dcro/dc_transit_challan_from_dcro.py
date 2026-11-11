# Copyright (c) 2026, Profezzo and contributors
# For license information, please see license.txt

"""DC Transit Challan from DCRO. DCRO portal, Billing System > AC Note Bill > DC Transit
Challan View (table gvDCDetails), read after Show. For every row the agent saves the
file of the Details button and of the AC Note Doc button; each has its own download column.
Data comes from Portal Data Extraction (agent) -> Portal Record; see procurement/portal_report.py.
Acceptance Note No, Net Weight (the Purchase Weight), Weight After Moisture Cut (the AC Note's own
Net Weight), Accepted Date and Moisture are read from the AC Note (portal_sync.add_net_weight).
Shown only in the report: Progressive Quantity (running total of Net Weight), Lots Delivered
(Progressive Quantity / Lot Quantity of Rice Lot Quantity, e.g. 500 / 290 = 1.72414) and No. of Bags
as a whole number ("580.00" -> "580").
Season filter (Kharif / Rabi) and District filter: only the DCs that View DC from DCRO shows with
that Season and District (for the same mill). Mill filter: the mill's own rows.
Accepted Date is a Date column (saved as dd-mm-yyyy text), so sorting goes by year, month, then day.
Rows are shown oldest Accepted Date first (rows without one last, the same date in portal order),
and Progressive Quantity / Lots Delivered run in that order."""

import json
import re

import frappe
from frappe.utils import flt, getdate

from ivri_od.procurement import dcro_filters
from ivri_od.procurement.portal_report import section_report
from ivri_od.procurement.portal_sync import ACCEPTED_DATE_COLUMN, NET_WEIGHT_COLUMN

SECTION = "DC Transit Challan"
# Column headers of the document buttons on the portal (also the section's Receipt Link Text).
DOCUMENTS = ["Details", "AC Note Doc"]
PROGRESSIVE_COLUMN = "Progressive Quantity"
LOTS_DELIVERED_COLUMN = "Lots Delivered"
# Portal header "No. of Bags(In kg.)": letters and digits only, lower case.
BAGS_KEY = "noofbags"
DC_COLUMN = "DC Order No"
# View DC from DCRO: the DC number and its Season ("KHARIF" / "RABI") columns.
VIEW_DC_SECTION = "View DC"
VIEW_DC_COLUMN = "DC Code(RRC)"
VIEW_DC_SEASON_COLUMN = "Season"
# District of the DC in View DC (read from the DC PDF, or set by hand there; see portal_sync.DISTRICT_COLUMN).
VIEW_DC_DISTRICT_COLUMN = "District"
KMS_YEAR_COLUMN = "KMS Year"  # e.g. 2025-26


def execute(filters=None):
	columns, data, *rest = section_report(
		filters,
		SECTION,
		site="DCRO",
		date_column=ACCEPTED_DATE_COLUMN,
		document_columns=DOCUMENTS,
		transform=report_cells,
		row_filter=dcro_row_filter(filters),
	)
	accepted_date_as_date(columns, data)
	return (columns, data, *rest)


def accepted_date_as_date(columns, data):
	"""Accepted Date as a Date column ("20-06-2026" -> 2026-06-20): sorted by date, shown in the
	system's date format. A cell that is not a dd-mm-yyyy date is left blank."""
	column = next((c for c in columns if c.get("label") == ACCEPTED_DATE_COLUMN), None)
	if not column:
		return
	column["fieldtype"] = "Date"
	column["width"] = 110
	for row in data:
		value = (row.get(column["fieldname"]) or "").strip()
		try:
			row[column["fieldname"]] = getdate(value, parse_day_first=True) if value else None
		except Exception:
			row[column["fieldname"]] = None


def dcro_row_filter(filters):
	"""Shared DCRO filters (dcro_filters.py): KMS Year from the row's own KMS Year; Season and
	District from the row's DC in View DC (season_filter). Season Both: every season."""
	_year, season, district = dcro_filters.parse_filters(filters)
	by_dc = season_filter(season, district)
	return dcro_filters.row_filter(filters, KMS_YEAR_COLUMN, extra=by_dc)


def season_filter(season, district=None):
	"""Keeps the rows whose DC (DC Order No) has this Season and/or this District in View DC, for the
	same mill; a DC not read in View DC yet (or with "No District Matched", when District is chosen) is
	left out. Case and extra spaces are ignored. None (all rows) when neither is chosen."""
	season = _match(season)
	district = _match(district)
	if not season and not district:
		return None
	dcs = set()
	for record in frappe.get_list(
		"Portal Record",
		filters={"site": "DCRO", "section": VIEW_DC_SECTION},
		fields=["mill_id", "row_data"],
		limit_page_length=0,
	):
		try:
			cells = json.loads(record.row_data or "{}") or {}
		except ValueError:
			continue
		if season and _match(cells.get(VIEW_DC_SEASON_COLUMN)) != season:
			continue
		if district and _match(cells.get(VIEW_DC_DISTRICT_COLUMN)) != district:
			continue
		dcs.add((record.mill_id or "", (cells.get(VIEW_DC_COLUMN) or "").strip()))
	return lambda record, cells: (record.mill_id or "", (cells.get(DC_COLUMN) or "").strip()) in dcs


def _match(text) -> str:
	"""" Kala handi " -> "kalahandi": case and spaces ignored."""
	return re.sub(r"\s+", "", (text or "")).lower()


def report_cells(records, cells_by_record: dict) -> dict:
	"""Progressive Quantity after Net Weight: Net Weight added up from the first row shown down
	to this row, per mill (rows of the report, in its order), then Lots Delivered (blank when
	Rice Lot Quantity has no Lot Quantity). No. of Bags without decimals."""
	lot_quantity = flt(frappe.db.get_single_value("Rice Lot Quantity", "lot_quantity"))
	out = {}
	totals = {}  # per mill
	for record in records:
		cells = {}
		for header, value in cells_by_record[record.name].items():
			cells[header] = _whole_number(value) if _key(header).startswith(BAGS_KEY) else value
			if header == NET_WEIGHT_COLUMN:
				mill = record.mill_id or ""
				totals[mill] = totals.get(mill, 0.0) + flt(str(value or "").replace(",", ""))
				cells[PROGRESSIVE_COLUMN] = f"{totals[mill]:.5f}"
				cells[LOTS_DELIVERED_COLUMN] = f"{totals[mill] / lot_quantity:.5f}" if lot_quantity else ""
		out[record.name] = cells
	return out


def _whole_number(value) -> str:
	"""580.00 -> 580; text that is not a number is kept as it is."""
	try:
		return str(round(float(str(value).replace(",", "").strip())))
	except ValueError:
		return value


def _key(text) -> str:
	return re.sub(r"[^a-z0-9]", "", (text or "").lower())
