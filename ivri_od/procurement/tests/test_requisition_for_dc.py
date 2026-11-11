# Copyright (c) 2026, Profezzo and contributors
"""DCRO Requisition for DC: section set-up, agent auto click and district names."""

import json

import frappe
from frappe.tests import IntegrationTestCase

from ivri_od.procurement.dcro_paddy_release import district_named_cells, district_named_header

DISTRICTS = {"balangir": "Balangir", "koraput": "Koraput", "sonepur town": "Sonepur Town"}


class TestRequisitionForDC(IntegrationTestCase):
	def test_district_names_as_paddy_release(self):
		own = "Balangir"
		self.assertEqual(district_named_header("Quantity (Own District) (in Qtl)", own, DISTRICTS), "Quantity Balangir (in Qtl)")
		self.assertEqual(
			district_named_header("Quantity (Other District)KORAPUT (in Qtl)", own, DISTRICTS), "Quantity Koraput (in Qtl)"
		)
		self.assertEqual(district_named_header("Qty (Other District) SONEPUR TOWN", own, DISTRICTS), "Qty Sonepur Town")
		# Unknown district, or no own District in Mill Master: header kept.
		self.assertEqual(district_named_header("Qty (Other District)XYZ", own, DISTRICTS), "Qty (Other District)XYZ")
		self.assertEqual(district_named_header("Qty (Own District)", None, DISTRICTS), "Qty (Own District)")
		self.assertEqual(district_named_header("Requisition No", own, DISTRICTS), "Requisition No")

	def test_cells_of_each_mill(self):
		records = [frappe._dict(name="R1", mill_id="M1"), frappe._dict(name="R2", mill_id="M2")]
		cells = {"R1": {"No": "1", "Qty (Own District)": "290"}, "R2": {"No": "2", "Qty (Own District)": "580"}}
		with (
			_patch("district_names", DISTRICTS),
			_patch("mill_districts", {"M1": "Balangir", "M2": "Koraput"}),
		):
			out = district_named_cells(records, cells)
		self.assertEqual(out["R1"], {"No": "1", "Qty Balangir": "290"})
		self.assertEqual(out["R2"], {"No": "2", "Qty Koraput": "580"})

	def test_section_and_agent_config(self):
		fixture = json.load(open(frappe.get_app_path("ivri_od", "fixtures", "portal_site.json")))
		dcro = next(site for site in fixture if site["name"] == "DCRO")
		section = next(s for s in dcro["sections"] if s["section_name"] == "Requisition for DC")
		self.assertEqual(section["page_match"], "MillerRqPDS")
		self.assertEqual(section["table_match"], "tabledata")
		self.assertEqual(section["auto_click_before_read"], '//*[@id="dvmillerhistory"]/a/i[1]')
		self.assertIn("#INTKMS", section["filter_columns"])
		self.assertIn("#ddlseason", section["filter_columns"])
		self.assertTrue(frappe.get_meta("Portal Site Section").has_field("auto_click_before_read"))


def _patch(name, value):
	from unittest.mock import patch

	return patch(f"ivri_od.procurement.dcro_paddy_release.{name}", return_value=value)
