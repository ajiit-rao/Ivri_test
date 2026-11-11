# Copyright (c) 2026, Profezzo and contributors
"""Joint Custody and Maintenance Charge Report: custody and maintenance charges payable to a
miller for one KMS Year, from the average paddy stock the mill held each month.

Filters: Miller Name (Mill), KMS Year, Season (Both / Kharif / Rabi) and District; no From / To Month.
One row per month: the Season Master Start Date - End Date of the chosen season(s), else the first to
the last month with data (as in Stock Account for Paddy). Movements before it make the Opening Balance.
Season: Transit Passes and Issue for Milling of that season only; Mill Paddy Transfer (no season of its
own) by Transfer Date within the season's Season Master dates (every transfer when they are not set).

Columns of a month:
- Opening Balance: Closing Balance of the month before (November: stock before 1 November).
- Receipt - Transfer from other Mill: submitted Mill Paddy Transfer entries (manual) of the mill
  and District, by Transfer Date.
- Receipt - PACS: paddy procured: PPAS Transit Pass quantity of the mill and KMS Year whose PPC is
  in the District (PPC Master), by Transit Pass Date (same as Stock Account for Paddy, PACs + WSHGs).
- Total = Opening Balance + Transfer + PACS.
- Issued for Milling: Paddy Stock Register's Issue for Milling (date-wise), summed for the month.
- Closing Balance = Total - Issued for Milling.
- OB+CB = Opening Balance + Closing Balance; OB+CB/2 = (Opening Balance + Closing Balance) / 2.

All data sources are read in ``get_entries``."""

from __future__ import annotations

from collections import defaultdict
from datetime import date

import frappe
from frappe import _
from frappe.utils import add_months, flt, getdate

from ivri_od.procurement.report.stock_account_for_paddy.stock_account_for_paddy import (
	BOTH_SEASONS,
	CROP_SEASONS,
	NO_END,
	get_issue_for_milling,
	get_kms_season_masters,
	get_kms_years,
	get_message,
	get_months,
	get_transit_passes,
	season_period,
	statement_period,
	tp_receipts,
)

PRECISION = 2
AVG_PRECISION = 3
# Rate per Qtl per month. ASSUMPTION: fixed at 2.40 until the client confirms where it comes from.
RATE_PER_QTL_PER_MONTH = 2.40

RECEIPTS = ("transfer", "pacs")
ISSUE = "issue"


def execute(filters=None):
	filters = frappe._dict(filters or {})
	crop_season = validate_filters(filters)
	seasons = get_kms_season_masters(filters.kms_year, crop_season)
	start, end = season_period(seasons)

	entries, skipped_passes = get_entries(filters, seasons, crop_season, start, end)
	from_date, to_date = statement_period(start, end, entries)
	opening, movements = split_entries(entries, from_date, to_date)
	rows = build_rows(get_months(from_date, to_date), opening, movements)
	summary = get_summary(rows, RATE_PER_QTL_PER_MONTH)
	data = [*rows, get_total_row(rows)]

	messages = [get_message(skipped_passes, frappe._dict(mill=filters.mill))]
	if crop_season and not (start and end):
		messages.append(
			_("Season Master {0} has no Start / End Date: every Mill Paddy Transfer is counted.").format(crop_season)
		)
	message = " ".join(m for m in messages if m) or None
	return get_columns(), data, message, None, get_report_summary(summary)


def validate_filters(filters):
	"""Miller Name (Mill), KMS Year, Season and District are needed; no months. Returns the crop
	season ("Kharif" / "Rabi"), or None for Both."""
	for fieldname, label in (
		("mill", _("Miller Name")),
		("kms_year", _("KMS Year")),
		("district", _("District")),
	):
		if not filters.get(fieldname):
			frappe.throw(_("{0} is mandatory").format(label))

	if filters.kms_year not in get_kms_years():
		frappe.throw(_("KMS Year {0} is not in Season Master").format(filters.kms_year))

	season = (filters.get("season") or BOTH_SEASONS).strip()
	if season not in (BOTH_SEASONS, *CROP_SEASONS):
		frappe.throw(_("Season must be Both, Kharif or Rabi"))
	filters.season = season
	return None if season == BOTH_SEASONS else season


def get_kms_months(kms_year) -> list[date]:
	"""First day of each month of the KMS Year: "24-25" -> 01-11-2024 ... 01-10-2025."""
	start = date(2000 + int(kms_year.split("-")[0]), 11, 1)
	return [getdate(add_months(start, i)) for i in range(12)]


def get_entries(filters, seasons, crop_season, start=None, end=None):
	"""THE ONLY PLACE THAT READS DATA.

	Returns ``(entries, skipped_passes)``:
	- ``entries``: ``[(date, "transfer" / "pacs" / "issue", qty)]`` of the season(s), up to ``end``.
	- ``skipped_passes``: Transit Passes of the mill not counted (PPC not in PPC Master / no District).
	"""
	to_date = end or NO_END
	paddy_filters = frappe._dict(mill=filters.mill, kms_year=filters.kms_year, paddy_account=filters.district)

	passes, skipped_passes = get_transit_passes(paddy_filters, [s.name for s in seasons], to_date)
	entries = [(day, "pacs", qty) for day, _column, qty in tp_receipts(passes)]  # PACS + WSHG procured
	# A transfer has no season: one season's report takes the transfers within its Season Master dates.
	entries += [
		entry
		for entry in get_transfers(filters, to_date)
		if not (crop_season and start and end) or start <= entry[0] <= end
	]
	entries += [
		(day, ISSUE, qty)
		for day, _column, qty in get_issue_for_milling(paddy_filters, to_date, crop_season=crop_season)
	]
	return [entry for entry in entries if entry[0] <= to_date], skipped_passes


def split_entries(entries, from_date, to_date):
	"""(opening, movements): paddy held before ``from_date``, and
	``{first day of month: {"transfer": qty, "pacs": qty, "issue": qty}}`` up to ``to_date``."""
	opening, movements = 0.0, defaultdict(lambda: defaultdict(float))
	for day, column, qty in entries:
		if day > to_date:
			continue
		if day < from_date:
			opening += -qty if column == ISSUE else qty
		else:
			movements[day.replace(day=1)][column] += qty
	return opening, movements


def get_transfers(filters, to_date):
	"""(Transfer Date, "transfer", qty) of submitted Mill Paddy Transfer entries of the mill and District."""
	rows = frappe.get_all(
		"Mill Paddy Transfer",
		filters={
			"docstatus": 1,
			"mill": filters.mill,
			"district": filters.district,
			"transfer_date": ["<=", to_date],
		},
		fields=["transfer_date", "quantity"],
		limit_page_length=0,
	)
	return [(getdate(row.transfer_date), "transfer", flt(row.quantity)) for row in rows]


def build_rows(months, opening, movements) -> list[dict]:
	rows, ob = [], flt(opening, PRECISION)
	for month in months:
		moved = movements.get(month, {})
		transfer = flt(moved.get("transfer"), PRECISION)
		pacs = flt(moved.get("pacs"), PRECISION)
		issue = flt(moved.get(ISSUE), PRECISION)
		total = flt(ob + transfer + pacs, PRECISION)
		cb = flt(total - issue, PRECISION)
		ob_cb = flt(ob + cb, PRECISION)
		rows.append(
			{
				"month": month.strftime("%b-%y"),
				"ob": ob,
				"transfer": transfer,
				"pacs": pacs,
				"total": total,
				"issue": issue,
				"cb": cb,
				"ob_cb": ob_cb,
				"ob_cb_half": flt(ob_cb / 2, AVG_PRECISION),
			}
		)
		ob = cb
	return rows


def get_total_row(rows) -> dict:
	"""Opening Balance, Total and Closing Balance are balances: their sum has no meaning, so blank."""
	total = {"month": _("Total"), "bold": 1, "ob": None, "total": None, "cb": None}
	for fieldname, precision in (
		("transfer", PRECISION),
		("pacs", PRECISION),
		("issue", PRECISION),
		("ob_cb", PRECISION),
		("ob_cb_half", AVG_PRECISION),
	):
		total[fieldname] = flt(sum(row[fieldname] for row in rows), precision)
	return total


def get_summary(rows, rate) -> dict:
	"""A to E of the paper statement. No receipt (B = 0): everything is 0, no division error."""
	average_paddy = flt(sum(row["ob_cb_half"] for row in rows), PRECISION)  # A
	received = flt(sum(row["transfer"] + row["pacs"] for row in rows), PRECISION)  # B
	average_period = flt(average_paddy / received, AVG_PRECISION) if received else 0.0  # C
	due_per_qtl = flt(average_period * flt(rate), PRECISION)  # D
	payable = flt(round(due_per_qtl * received), PRECISION)  # E, nearest rupee
	return {
		"average_paddy": average_paddy,
		"received": received,
		"average_period": average_period,
		"due_per_qtl": due_per_qtl,
		"payable": payable,
	}


def get_report_summary(summary) -> list[dict]:
	return [
		{"label": _("A. Total Average Paddy (Qtl)"), "value": summary["average_paddy"], "datatype": "Float"},
		{"label": _("B. Total Paddy Received (Qtl)"), "value": summary["received"], "datatype": "Float"},
		{"label": _("C. Total Average Period (Months)"), "value": summary["average_period"], "datatype": "Float"},
		{"label": _("D. Custody Maintenance Due (per Qtl)"), "value": summary["due_per_qtl"], "datatype": "Float"},
		{
			"label": _("E. Joint & Custody Maintenance Payable to Miller"),
			"value": summary["payable"],
			"datatype": "Currency",
			"currency": "INR",
			"indicator": "Green",
		},
	]


def get_columns():
	columns = [{"label": _("Month"), "fieldname": "month", "fieldtype": "Data", "width": 90}]
	for label, fieldname, precision, width in (
		(_("Opening Balance"), "ob", PRECISION, 140),
		(_("Receipt - Transfer from other Mill"), "transfer", PRECISION, 200),
		(_("Receipt - PACS"), "pacs", PRECISION, 140),
		(_("Total"), "total", PRECISION, 130),
		(_("Issued for Milling"), "issue", PRECISION, 150),
		(_("Closing Balance"), "cb", PRECISION, 140),
		(_("OB+CB"), "ob_cb", PRECISION, 130),
		(_("OB+CB/2"), "ob_cb_half", AVG_PRECISION, 130),
	):
		columns.append(
			{"label": label, "fieldname": fieldname, "fieldtype": "Float", "precision": precision, "width": width}
		)
	return columns
