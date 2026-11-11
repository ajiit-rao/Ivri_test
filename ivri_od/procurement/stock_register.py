# Copyright (c) 2026, Profezzo and contributors
"""Shared logic of the day-wise stock registers (Paddy Stock Register, Rice Stock Register).

- Filters: Mill Name (Mill Master), KMS Year ("25-26"), Season (Both / Kharif / Rabi), District
  (District Master, printed as "AC - <District>"). No From / To Date (as in Stock Account for Paddy).
- Season from Season Master (KMS Year + Kharif / Rabi; Both = the two). Start / End Date are
  optional: the data is already of that KMS Year and season, so without a Start Date "Prog."
  totals count every movement up to the day; with one, they count from it.
- Days shown (set_period): Season Master Start Date - End Date (not past today), else the first
  to the last day with data.
- day_rows(): one entry per day with O.B., the day's movements, progressive totals and C.B.
  Each report turns these into its own columns.
"""

from __future__ import annotations

import datetime
from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import add_days, date_diff, flt, getdate

from ivri_od.procurement.report.stock_account_for_paddy.stock_account_for_paddy import (
	BOTH_SEASONS,
	CROP_SEASONS,
	NO_END,
	get_kms_season_masters,
	season_master_year,
	season_period,
)

SEASONS = CROP_SEASONS


ALL_DISTRICTS = "All Districts"


def validate_filters(filters, district_required=True):
	"""Check the common filters, set filters.company, filters.ac (the District filter),
	filters.season ("Both" / "Kharif" / "Rabi"), filters.crop_season (None for Both) and
	filters.to_date (upper limit for reading data; set_period() sets the real days). Returns the
	season(s): frappe._dict(names, start_date, end_date).

	With ``district_required=False`` the District may be blank: filters.district stays empty
	(= all districts) and filters.ac is "All Districts"."""
	mandatory = [
		("mill", _("Mill Name")),
		("kms_year", _("KMS Year")),
		("district", _("District")),
	]
	if not district_required:
		mandatory = [m for m in mandatory if m[0] != "district"]
	for fieldname, label in mandatory:
		if not filters.get(fieldname):
			frappe.throw(_("{0} is mandatory").format(label))

	season = (filters.get("season") or BOTH_SEASONS).strip()
	if season not in (BOTH_SEASONS, *SEASONS):
		frappe.throw(_("Season must be Both, Kharif or Rabi"))
	filters.season = season
	filters.crop_season = None if season == BOTH_SEASONS else season

	# The mill's company and the District account (AC) are printed in the heading.
	filters.company = frappe.db.get_value("Mill Master", filters.mill, "company")
	if not filters.company:
		frappe.throw(_("Set the Company in Mill Master {0}").format(filters.mill))
	if filters.get("district"):
		if not frappe.db.exists("District Master", filters.district):
			frappe.throw(_("District {0} not found").format(filters.district))
		filters.ac = filters.district
	else:
		filters.district = None
		filters.ac = ALL_DISTRICTS

	seasons = get_seasons(filters.kms_year, filters.crop_season)
	filters.from_date = None
	filters.to_date = seasons.end_date or NO_END
	return seasons


def get_seasons(kms_year, crop_season=None):
	"""Season Master(s) of the KMS Year: only ``crop_season``'s, or Kharif and Rabi when None.
	start_date / end_date: earliest Start / latest End Date, None unless every season has it."""
	masters = get_kms_season_masters(kms_year, crop_season)  # stops when there is none
	start, end = season_period(masters)
	return frappe._dict(names=[m.name for m in masters], start_date=start, end_date=end)


def season_matches(value, crop_season):
	"""True when a row's Season (e.g. "KHARIF") is ``crop_season``, or Kharif / Rabi for Both (None).
	Rows without a Season never match."""
	value = (value or "").strip().casefold()
	if crop_season:
		return value == crop_season.casefold()
	return value in {s.casefold() for s in SEASONS}


def set_period(filters, seasons, movements):
	"""Set filters.from_date / to_date: the Season Master Start - End Date (End not later than today,
	unless there is data after today), else the first to the last day of the movements; today when
	there is no data at all."""
	dates = [getdate(movement[0]) for movement in movements]
	today = getdate()
	last = max(dates) if dates else today
	from_date = seasons.start_date or (min(dates) if dates else today)
	to_date = min(seasons.end_date, max(today, last)) if seasons.end_date else last
	filters.from_date, filters.to_date = from_date, max(to_date, from_date)


def get_title(register, filters):
	"""e.g. "PADDY STOCK REGISTER KMS 2025-26 M/s <Company> , AC - <AC>, Kharif" ("Kharif & Rabi" for Both)."""
	kms = f"20{filters.kms_year}" if filters.kms_year else ""
	season = " & ".join(SEASONS) if filters.season == BOTH_SEASONS else filters.season
	return f"{register} KMS {kms} M/s {filters.company} , AC - {filters.ac}, {season}"


def day_rows(season_start, from_date, to_date, season_opening, movements, receipts, disposals, others=()):
	"""One entry per day From Date -> To Date (days without movement included).

	movements: (date, kind, qty). ``receipts`` add to stock, ``disposals`` reduce it, ``others``
	(e.g. Release Order) are only counted. Movements before the season start or of other kinds are
	ignored; those before From Date go into the first O.B. and the progressive totals.

	Each entry: date, ob, day ({kind: qty}, only kinds with an entry that day), prog ({kind: qty}
	from season start up to and including the day), total_stock, cb, mismatch (1 when
	C.B. != season opening + progressive receipts - progressive disposals).
	"""
	# No season start (Season Master without Start Date): count every movement before From Date.
	season_start = getdate(season_start) if season_start else datetime.date.min
	from_date, to_date = getdate(from_date), getdate(to_date)
	kinds = (*receipts, *disposals, *others)

	by_day = defaultdict(lambda: defaultdict(float))
	prog = defaultdict(float)
	for date, kind, qty in movements:
		date = getdate(date)
		if kind not in kinds or date < season_start or date > to_date:
			continue
		if date < from_date:
			prog[kind] += flt(qty)
		else:
			by_day[date][kind] += flt(qty)

	def total(qty_by_kind, of_kinds):
		return sum(flt(qty_by_kind.get(kind, 0)) for kind in of_kinds)

	ob = flt(season_opening) + total(prog, receipts) - total(prog, disposals)
	entries = []
	for i in range(date_diff(to_date, from_date) + 1):
		date = add_days(from_date, i)
		day = dict(by_day.get(date, {}))
		for kind, qty in day.items():
			prog[kind] += qty

		total_stock = ob + total(day, receipts)
		cb = total_stock - total(day, disposals)
		expected = flt(season_opening) + total(prog, receipts) - total(prog, disposals)
		entries.append(
			frappe._dict(
				date=date,
				ob=ob,
				day=day,
				prog=dict(prog),
				total_stock=total_stock,
				cb=cb,
				mismatch=int(abs(expected - cb) > 0.00005),
			)
		)
		ob = cb  # next day's O.B. is this day's C.B.
	return entries


def get_message(title, rows, extra=()):
	"""Title line on screen, then warnings (red)."""
	parts = [f"<div style='font-weight:bold;text-align:center'>{frappe.utils.escape_html(title)}</div>"]
	mismatches = sum(1 for row in rows if row.mismatch)
	if mismatches:
		parts.append(
			_("{0} day(s) where C.B. does not match season opening + Prog. Receipt - Prog. Disposal.").format(
				mismatches
			)
		)
	parts.extend(extra)
	return parts[0] + "".join(f"<div style='color:red'>{p}</div>" for p in parts[1:])
