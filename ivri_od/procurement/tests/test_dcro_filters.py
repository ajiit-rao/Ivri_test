# Copyright (c) 2026, Profezzo and contributors
"""Shared filters of the DCRO Details reports: KMS Year, Season (Both / Kharif / Rabi), District."""

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from ivri_od.procurement import dcro_filters

DISTRICTS = {"balangir": "Balangir", "koraput": "Koraput"}


def keep(row_filter, cells, mill="M1"):
	return row_filter(frappe._dict(mill_id=mill), cells)


class TestDCROFilters(IntegrationTestCase):
	def test_parse(self):
		self.assertEqual(dcro_filters.parse_filters({}), (None, None, None))  # Both, every year, every district
		self.assertEqual(dcro_filters.parse_filters({"kms_year": "25-26", "season": "rabi", "district": "Koraput"}), (2025, "Rabi", "Koraput"))
		self.assertRaises(frappe.ValidationError, dcro_filters.parse_filters, {"season": "Summer"})
		self.assertIsNone(dcro_filters.row_filter({"season": "Both"}, "KMS Year", "Season"))

	def test_kms_year_and_season(self):
		f = dcro_filters.row_filter({"kms_year": "25-26", "season": "Kharif"}, "KMS Year", "Season")
		self.assertTrue(keep(f, {"KMS Year": "2025-2026", "Season": "KHARIF"}))
		self.assertTrue(keep(f, {"KMS Year": "2025-26", "Season": "Kharif"}))
		self.assertFalse(keep(f, {"KMS Year": "2025-2026", "Season": "Rabi"}))
		self.assertFalse(keep(f, {"KMS Year": "2024-2025", "Season": "Kharif"}))
		both = dcro_filters.row_filter({"kms_year": "25-26", "season": "Both"}, "KMS Year", "Season")
		self.assertTrue(keep(both, {"KMS Year": "2025-2026", "Season": "Rabi"}))

	def test_district_column(self):
		f = dcro_filters.row_filter({"district": "Balangir"}, district_of=dcro_filters.district_column())
		self.assertTrue(keep(f, {"District": "BALANGIR "}))
		self.assertFalse(keep(f, {"District": "Koraput"}))

	def test_district_in_headers_as_paddy_release(self):
		with (
			patch.object(dcro_filters, "district_names", return_value=DISTRICTS),
			patch.object(dcro_filters, "mill_districts", return_value={"M1": "Balangir"}),
		):
			own = dcro_filters.row_filter({"district": "Balangir"}, district_of=dcro_filters.district_in_headers())
			other = dcro_filters.row_filter({"district": "Koraput"}, district_of=dcro_filters.district_in_headers())
		row = {
			"Quantity of Requistion (Own District) (in Qtl)": "2610.00",
			"Quantity of Requistion (Other District)KORAPUT (in Qtl)": "0.00",
		}
		self.assertTrue(keep(own, row))  # Own District = the mill's District (Balangir)
		self.assertFalse(keep(other, row))  # Koraput's column is 0
		self.assertTrue(keep(other, {**row, "Quantity of Requistion (Other District)KORAPUT (in Qtl)": "580"}))
		self.assertFalse(keep(own, row, mill="M2"))  # a mill without a District in Mill Master
