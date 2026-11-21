# Copyright (c) 2026, Profezzo and contributors
"""New NBT Gunny Account: monthly OB, receipts, other, issues by District and CB of gunny bags, OSCSC and PP.

Filters: Mill, KMS Year (those with Transit Passes of the mill) and Season (Both / Kharif / Rabi).
No From / To Month: the months are the first to the last month with data.
OSCSC:
- Receipts: SCMS Gunny Stock Register Details of the mill, columns C + D + E (Road, Rake, Concor),
  by its Date - A month. Only the rows read with that KMS Year and Season on the SCMS page (the KMS Year
  and Season columns the agent saves from its drop-downs); rows read before those columns existed have
  none and are not counted (the report says how many).
- Other: the same rows, columns F + G + H + I + J (transfers).
- Issue <District>: lots delivered x No. of Bags per Lot (Rice Lot Quantity). Lots delivered: DCRO
  DC Transit Challan rows with an Accepted Date (by that month; District of the DC in View DC) and
  SCMS Lot Search rows with Challan Status Accepted (by Receipt Date month; their District).
  One Issue column per District the mill procured from in the KMS Year (Districts of the PPCs of
  its Transit Passes, see Stock Account for Paddy), 0 while nothing is delivered there yet; also
  for a District with lots or PP bags but no Transit Pass.
  Season Kharif / Rabi: only the lots of DCs whose Season in DCRO View DC is that season (as in Rice
  Stock Report).
PP: typed in the report (click a PP cell of a month), saved in Gunny PP Entry. It has no Season, so it
counts for every Season.
Total Receipts = OB + Receipts + Other; Total Issue = all Districts; CB = Total Receipts - Total Issue.
OB of a month = CB of the month before (the first month starts at 0). Total row: no OB,
Total Receipts = Receipts + Other, CB of the last month."""

from __future__ import annotations

import re
from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import cint, get_first_day, get_last_day, getdate

from ivri_od.procurement.dcro_paddy_release import district_names
from ivri_od.procurement.portal_report import _load
from ivri_od.procurement.report.stock_account_for_paddy.stock_account_for_paddy import (
	BOTH_SEASONS,
	CROP_SEASONS,
	NO_END,
	dcro_kms_year,
	get_kms_seasons,
	get_kms_years,
	get_months,
	parse_portal_date,
	procured_districts,
	season_master_year,
)

BAG_TYPES = ("oscsc", "pp")
RECEIPTS = ("receipts", "other")
# Gunny Stock Register Details: column letters at the end of the header ("... - ROAD - C").
REGISTER_SECTION = "Gunny Stock Register Details"
REGISTER_DATE_COLUMN = "Date - A"
# Saved from the SCMS page's drop-downs (#ddlKmsYear, #ddlSeason; the section's Page Filter Columns).
REGISTER_KMS_COLUMN = "KMS Year"
REGISTER_SEASON_COLUMN = "Season"
REGISTER_LETTERS = {"receipts": ("C", "D", "E"), "other": ("F", "G", "H", "I", "J")}
REGISTER_LETTER = re.compile(r"-\s*([A-Z])\s*$")
# DCRO DC Transit Challan, its District from View DC (DC Order No = DC Code(RRC)).
TRANSIT_SECTION = "DC Transit Challan"
TRANSIT_DC_COLUMN = "DC Order No"
TRANSIT_DATE_COLUMN = "Accepted Date"
VIEW_DC_SECTION = "View DC"
VIEW_DC_COLUMN = "DC Code(RRC)"
# SCMS Lot Search.
LOT_SEARCH_SECTION = "Lot Search"
LOT_SEARCH_DATE_COLUMN = "Receipt Date"
LOT_SEARCH_STATUS = "accepted"
# Gunny PP Entry account of each column (Issue: one per District).
PP_ACCOUNTS = {"receipts": "Receipts", "other": "Other"}


def execute(filters=None):
	filters = frappe._dict(filters or {})
	validate_filters(filters)
	to_date = NO_END

	if filters.kms_year not in get_kms_years(filters.mill):
		# No Transit Pass of the mill in the KMS Year: no statement.
		return get_columns([]), [], _("Mill {0} has no Transit Pass data in KMS Year {1}.").format(
			filters.mill, filters.kms_year
		)

	movements, without_season = get_movements(filters, to_date)
	districts = procured_districts(filters.mill, get_kms_seasons(filters.kms_year), to_date)
	districts = sorted(districts | {district for _date, column, district, _type, _bags in movements if column == "issue"})
	from_date, to_date = data_months(movements)
	opening, by_month = classify(movements, from_date)
	message = None
	if without_season:
		message = _(
			"{0} Gunny Stock Register Details rows of mill {1} have no KMS Year / Season and are not counted. "
			"Read the SCMS Gunny Stock Register page again with the PPAS Agent (KMS Year and Season set)."
		).format(without_season, filters.mill)
	return get_columns(districts), build_rows(get_months(from_date, to_date), districts, opening, by_month), message


def data_months(movements):
	"""(first day of the first month, last day of the last month) with data; this month without data."""
	dates = [getdate(movement[0]) for movement in movements if movement[0]]
	today = getdate()
	return getdate(get_first_day(min(dates) if dates else today)), getdate(get_last_day(max(dates) if dates else today))


def validate_filters(filters):
	"""Mill, KMS Year and Season (Both / Kharif / Rabi). Sets filters.crop_season (None for Both) and
	filters.company (printed in the heading)."""
	for fieldname, label in (
		("mill", _("Mill Name")),
		("kms_year", _("KMS Year")),
	):
		if not filters.get(fieldname):
			frappe.throw(_("{0} is mandatory").format(label))
	season = (filters.get("season") or BOTH_SEASONS).strip()
	if season not in (BOTH_SEASONS, *CROP_SEASONS):
		frappe.throw(_("Season must be Both, Kharif or Rabi"))
	filters.season = season
	filters.crop_season = None if season == BOTH_SEASONS else season

	# The mill's company is printed in the heading.
	filters.company = frappe.db.get_value("Mill Master", filters.mill, "company")
	if not filters.company:
		frappe.throw(_("Set the Company in Mill Master {0}").format(filters.mill))


def issue_key(district):
	return f"issue_{frappe.scrub(district)}"


def get_columns(districts):
	groups = [("ob", _("OB")), ("receipts", _("Receipts")), ("other", _("Other")), ("total_receipts", _("Total Receipts"))]
	groups += [(issue_key(district), _("Issue {0}").format(district)) for district in districts]
	groups += [("total_issue", _("Total Issue")), ("cb", _("CB"))]
	columns = [{"label": _("Month"), "fieldname": "month", "fieldtype": "Data", "width": 90}]
	for group, label in groups:
		for bag_type in BAG_TYPES:
			columns.append(
				{"label": f"{label} - {bag_type.upper()}", "fieldname": f"{group}_{bag_type}", "fieldtype": "Int", "width": 120}
			)
	return columns


def get_movements(filters, to_date):
	"""(movements, register rows without KMS Year / Season). Movements: gunny bags of the mill, KMS Year
	and Season, as (date, column, District, bag type, bags): column "receipts", "other" or "issue"
	(District set only for "issue"). Season Master Start / End Date are never used."""
	from ivri_od.procurement.report.rice_stock_report.rice_stock_report import get_season_dcs

	year = cint(season_master_year(filters.kms_year))
	without_season = []
	movements = register_movements(
		filters.mill, None, to_date, kms_year=year, crop_season=filters.crop_season, without_season=without_season
	)
	season_dcs, _without = get_season_dcs(filters.mill, filters.crop_season)
	movements += issue_movements(filters.mill, year, to_date, season_dcs=season_dcs)
	movements += pp_movements(filters.mill, filters.kms_year, to_date)
	return movements, len(without_season)


def register_movements(mill, from_date, to_date, kms_year=None, crop_season=None, without_season=None):
	"""OSCSC receipts and other receipts from the Gunny Stock Register Details rows (the Total row is skipped).

	With ``kms_year`` (first year, e.g. 2025): only the rows of that KMS Year and of ``crop_season``
	(Kharif / Rabi; None = both), from their KMS Year and Season columns; a row without them is left out
	and added to the ``without_season`` list."""
	movements = []
	for record in _portal_rows("SCMS", REGISTER_SECTION, mill):
		cells = _load(record.row_data)
		row_date = parse_portal_date(cells.get(REGISTER_DATE_COLUMN))
		if not row_date or row_date > to_date or (from_date and row_date < from_date):
			continue
		if kms_year:
			row_kms = dcro_kms_year(cells.get(REGISTER_KMS_COLUMN))
			row_season = (cells.get(REGISTER_SEASON_COLUMN) or "").strip().casefold()
			if not row_kms or not row_season:
				if without_season is not None:
					without_season.append(row_date)
				continue
			if row_kms != kms_year or not register_season_matches(row_season, crop_season):
				continue
		for column, bags in register_bags(cells).items():
			if bags:
				movements.append((row_date, column, "", "oscsc", bags))
	return movements


def register_season_matches(row_season, crop_season):
	"""The row's Season (e.g. "KHARIF") is ``crop_season``, or Kharif / Rabi for Both (None)."""
	seasons = [crop_season] if crop_season else list(CROP_SEASONS)
	return any(row_season.startswith(season.casefold()) for season in seasons)


def register_bags(cells):
	"""{"receipts": C + D + E, "other": F + G + H + I + J} of one register row."""
	by_letter = {}
	for header, value in cells.items():
		match = REGISTER_LETTER.search(header)
		if match:
			by_letter[match.group(1)] = cint(str(value or "").replace(",", ""))
	return {column: sum(by_letter.get(letter, 0) for letter in letters) for column, letters in REGISTER_LETTERS.items()}


def issue_movements(mill, year, to_date, season_dcs=None):
	"""OSCSC issues by District: one lot (No. of Bags per Lot) per accepted DC Transit Challan row
	(District of its DC in View DC) and per accepted Lot Search row (its District).
	``season_dcs``: DC numbers of one season (View DC); None = every DC (Both seasons)."""
	from ivri_od.procurement.report.rice_stock_report.rice_stock_report import _dc_key

	bags_per_lot = cint(frappe.db.get_single_value("Rice Lot Quantity", "bags_per_lot"))
	districts = district_names()
	lots = []

	dc_district = {}
	for record in _portal_rows("DCRO", VIEW_DC_SECTION, mill):
		cells = _load(record.row_data)
		dc_district[(cells.get(VIEW_DC_COLUMN) or "").strip()] = cells.get("District")
	for record in _portal_rows("DCRO", TRANSIT_SECTION, mill):
		cells = _load(record.row_data)
		if dcro_kms_year(cells.get("KMS Year")) == year:
			if season_dcs is not None and _dc_key(cells.get(TRANSIT_DC_COLUMN)) not in season_dcs:
				continue
			district = dc_district.get((cells.get(TRANSIT_DC_COLUMN) or "").strip())
			lots.append((parse_portal_date(cells.get(TRANSIT_DATE_COLUMN)), district))

	for record in _portal_rows("SCMS", LOT_SEARCH_SECTION, mill):
		cells = _load(record.row_data)
		accepted = (cells.get("Challan Status") or "").strip().lower() == LOT_SEARCH_STATUS
		if accepted and dcro_kms_year(cells.get("KMS Year")) == year:
			if season_dcs is not None and _dc_key(cells.get("DC No.")) not in season_dcs:
				continue
			lots.append((parse_portal_date(cells.get(LOT_SEARCH_DATE_COLUMN)), cells.get("District")))

	if lots and not bags_per_lot:
		frappe.throw(_("Set the No. of Bags per Lot in Rice Lot Quantity"))
	return [
		(lot_date, "issue", district_label(district, districts), "oscsc", bags_per_lot)
		for lot_date, district in lots
		if lot_date and lot_date <= to_date
	]


def district_label(district, districts):
	"""District as spelt in District Master ("BALANGIR" -> "Balangir"), else as on the portal."""
	district = (district or "").strip()
	return districts.get(district.casefold()) or district or _("No District")


def pp_movements(mill, kms_year, to_date):
	"""PP bags typed in the report (Gunny PP Entry)."""
	movements = []
	for entry in frappe.get_all(
		"Gunny PP Entry",
		filters={"mill": mill, "kms_year": kms_year, "month": ["<=", to_date]},
		fields=["month", "account", "district", "bags"],
	):
		column = {label: key for key, label in PP_ACCOUNTS.items()}.get(entry.account, "issue")
		movements.append((getdate(entry.month), column, entry.district or "", "pp", cint(entry.bags)))
	return movements


def _portal_rows(site, section, mill):
	return frappe.get_all(
		"Portal Record",
		filters={"site": site, "section": section, "mill_id": mill},
		fields=["row_data"],
		limit_page_length=0,
	)


def classify(movements, from_date):
	"""Return ({bag type: opening bags}, {month: {"<group>_<bag type>": bags}})."""
	opening = {bag_type: 0 for bag_type in BAG_TYPES}
	by_month = defaultdict(lambda: defaultdict(int))
	for movement_date, column, district, bag_type, bags in movements:
		movement_date, bags = getdate(movement_date), cint(bags)
		if movement_date < from_date:
			opening[bag_type] += -bags if column == "issue" else bags
		else:
			group = issue_key(district) if column == "issue" else column
			by_month[movement_date.replace(day=1)][f"{group}_{bag_type}"] += bags
	return opening, by_month


def build_rows(months, districts, opening, movements):
	"""One row per month (zero rows included), then the TOTAL row. A month row also carries its
	first day (month_date) and the District of each Issue PP cell (pp_districts), for editing PP."""
	issues = [issue_key(district) for district in districts]
	pp_districts = {f"{issue_key(district)}_pp": district for district in districts}
	rows, balance = [], dict(opening)
	for month in months:
		month_movements = movements.get(month) or {}
		row = {"month": month.strftime("%b-%y"), "month_date": str(month), "pp_districts": pp_districts}
		for bag_type in BAG_TYPES:
			row[f"ob_{bag_type}"] = balance[bag_type]
			for group in RECEIPTS + tuple(issues):
				row[f"{group}_{bag_type}"] = cint(month_movements.get(f"{group}_{bag_type}"))
			set_totals(row, bag_type, issues, with_ob=True)
			balance[bag_type] = row[f"cb_{bag_type}"]
		rows.append(row)

	rows.append(get_total_row(rows, issues))
	return rows


def set_totals(row, bag_type, issues, with_ob):
	"""Total Receipts = OB + Receipts + Other (TOTAL row: without OB), Total Issue, CB."""
	ob = row[f"ob_{bag_type}"] if with_ob else 0
	row[f"total_receipts_{bag_type}"] = ob + sum(row[f"{group}_{bag_type}"] for group in RECEIPTS)
	row[f"total_issue_{bag_type}"] = sum(row[f"{group}_{bag_type}"] for group in issues)
	row[f"cb_{bag_type}"] = row[f"total_receipts_{bag_type}"] - row[f"total_issue_{bag_type}"]


def get_total_row(month_rows, issues):
	"""OB blank, period sums of receipts and issues, CB of the last month."""
	total_row = {"month": _("TOTAL"), "bold": 1}
	for bag_type in BAG_TYPES:
		total_row[f"ob_{bag_type}"] = None
		for group in RECEIPTS + tuple(issues):
			total_row[f"{group}_{bag_type}"] = sum(row[f"{group}_{bag_type}"] for row in month_rows)
		set_totals(total_row, bag_type, issues, with_ob=False)
		total_row[f"cb_{bag_type}"] = month_rows[-1][f"cb_{bag_type}"] if month_rows else 0
	return total_row


@frappe.whitelist(methods=["POST"])
def set_pp_bags(mill: str, kms_year: str, month: str, account: str, district: str | None = None, bags: int | None = None) -> int:
	"""Save the PP bags of one cell of the report (Gunny PP Entry); empty or 0 removes the entry.
	``account``: "Receipts", "Other" or "Issue" (with its District). Returns the bags saved."""
	if account not in ("Receipts", "Other", "Issue"):
		frappe.throw(_("PP bags can be set only for Receipts, Other or an Issue"))
	frappe.has_permission("Gunny PP Entry", "create", throw=True)
	if not frappe.db.exists("Mill Master", mill):
		frappe.throw(_("Mill {0} is not in Mill Master").format(mill))
	if account == "Issue" and not frappe.db.exists("District Master", district):
		frappe.throw(_("District {0} is not available in District Master").format(frappe.bold(district or "")))
	bags = cint(bags)
	if bags < 0:
		frappe.throw(_("PP bags cannot be negative"))

	month = getdate(get_first_day(month))
	district = district if account == "Issue" else None
	name = frappe.db.exists(
		"Gunny PP Entry",
		{"mill": mill, "kms_year": kms_year, "month": month, "account": account, "district": district or ("is", "not set")},
	)
	if not bags:
		if name:
			frappe.delete_doc("Gunny PP Entry", name)
		return 0
	doc = frappe.get_doc("Gunny PP Entry", name) if name else frappe.new_doc("Gunny PP Entry")
	doc.update({"mill": mill, "kms_year": kms_year, "month": month, "account": account, "district": district, "bags": bags})
	doc.save()
	return doc.bags
