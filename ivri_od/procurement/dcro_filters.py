# Copyright (c) 2026, Profezzo and contributors
"""Filters shared by the DCRO Details reports (Paddy Release, View DC, DC Transit Challan and
Requisition for DC from DCRO): Mill Name, KMS Year ("25-26"), Season (Both / Kharif / Rabi) and
District. Empty KMS Year or District, or Season Both: no filter on it.

Each report says where a row's KMS Year, Season and District are:
- KMS Year / Season: a column of the row (the page's #INTKMS / #ddlseason, or View DC's own).
- District: a "District" column (View DC), or the "(Own District)" / "(Other District)NAME"
  quantity columns as in Paddy Release (Own District = the mill's District in Mill Master):
  a row is of the District when one of its columns of that District has a quantity."""

from __future__ import annotations

import re

import frappe
from frappe import _

from ivri_od.procurement.dcro_paddy_release import (
	OTHER_DISTRICT,
	OWN_DISTRICT,
	_known_district,
	_number,
	district_names,
	mill_districts,
)

BOTH_SEASONS = "Both"
SEASONS = ("Kharif", "Rabi")


def parse_filters(filters) -> tuple:
	"""(KMS first year e.g. 2025 or None, "Kharif" / "Rabi" or None for Both, District or None)."""
	# Imported here: Stock Account for Paddy imports Paddy Release from DCRO, which imports this module.
	from ivri_od.procurement.report.stock_account_for_paddy.stock_account_for_paddy import season_master_year

	filters = filters or {}
	season = (filters.get("season") or BOTH_SEASONS).strip()
	if season.casefold() == BOTH_SEASONS.casefold():
		season = None
	elif season.title() in SEASONS:
		season = season.title()
	else:
		frappe.throw(_("Season must be Both, Kharif or Rabi"))
	kms_year = (filters.get("kms_year") or "").strip()
	year = int(season_master_year(kms_year)) if kms_year else None
	return year, season, (filters.get("district") or "").strip() or None


def row_filter(filters, kms_column=None, season_column=None, district_of=None, extra=None):
	"""row_filter(record, cells) for portal_report.section_report, or None when nothing is chosen.
	``district_of(record, cells, district)`` -> True when the row is of the District;
	``extra(record, cells)``: the report's own check (e.g. View DC's From / To Month)."""
	from ivri_od.procurement.report.stock_account_for_paddy.stock_account_for_paddy import dcro_kms_year

	year, season, district = parse_filters(filters)
	year = year if kms_column else None
	season = season if season_column else None
	district = district if district_of else None
	if not (year or season or district or extra):
		return None

	def keep(record, cells):
		if year and dcro_kms_year(cells.get(kms_column)) != year:
			return False
		if season and _match(cells.get(season_column)) != _match(season):
			return False
		if district and not district_of(record, cells, district):
			return False
		return not extra or extra(record, cells)

	return keep


def district_column(column="District"):
	"""district_of for a row with its own District column (View DC)."""
	return lambda record, cells, district: _match(cells.get(column)) == _match(district)


def district_in_headers():
	"""district_of for rows with "(Own District)" / "(Other District)NAME" quantity columns
	(Paddy Release, Requisition for DC): one of the District's columns has a quantity."""
	districts, mills = district_names(), mill_districts()

	def of_district(record, cells, district):
		wanted = _match(district)
		own = mills.get(record.mill_id or "")
		for header, value in cells.items():
			if not _number(value):
				continue
			if OWN_DISTRICT.search(header or ""):
				if own and _match(own) == wanted:
					return True
				continue
			match = OTHER_DISTRICT.search(header or "")
			if match:
				named = (match.group(2) and _known_district(f"{match.group(1)} {match.group(2)}", districts)) or (
					_known_district(match.group(1), districts)
				)
				if named and _match(named) == wanted:
					return True
		return False

	return of_district


def _match(text) -> str:
	return re.sub(r"\s+", "", str(text or "")).casefold()
