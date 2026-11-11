# Copyright (c) 2026, Profezzo and contributors

import json
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from ivri_od.procurement.report.dc_details.dc_details import _add_pending, _dc_lots, _in_season, _line, _total

RAW = frappe._dict(rice_type="Raw", cmr_percentage=67, driage_percentage=0.078)
BOILED = frappe._dict(rice_type="Boiled", cmr_percentage=68, driage_percentage=0)


class TestDCDetails(IntegrationTestCase):
	def test_figures_as_in_dc_details_sheet(self):
		# Figures of the Kharif 25-26 DC Details sheet (SSPP BLD and SSPP RAW).
		boiled = _line(
			frappe._dict(name="M1", company="SSPP BLD", type="BOILED", lot_quantity=290),
			BOILED,
			78534.02,
			{"fci_issue": 90, "fci_delivery": 84, "rrc_issue": 40, "rrc_delivery": 39},
		)
		self.assertEqual(boiled["driage"], 0)
		self.assertEqual(boiled["cmr_due"], 53403.13)
		self.assertEqual(boiled["total_lot"], 184)
		self.assertEqual((boiled["fci_balance"], boiled["rrc_balance"]), (6, 1))
		self.assertEqual((boiled["total_delivery"], boiled["total_dc_issued"]), (123, 130))
		self.assertEqual((boiled["total_dc_issue_balance"], boiled["total_delivery_balance"]), (54, 61))
		self.assertEqual(boiled["vr_pending"], -130)  # no requisition read - (90 + 40) DCs issued
		self.assertEqual(boiled["delivery_percent"], 66.79)

		raw = _line(
			frappe._dict(name="M2", company="SSPP RAW", type="RAW", lot_quantity=290),
			RAW,
			58372.69,
			{"fci_issue": 42, "fci_delivery": 39},
		)
		self.assertEqual(raw["driage"], 45.53)
		self.assertEqual(raw["paddy_after_driage"], 58327.16)
		self.assertEqual(raw["cmr_due"], 39079.2)
		self.assertEqual(raw["total_lot"], 135)
		self.assertEqual(raw["delivery_percent"], 28.94)

		total = _total([boiled, raw])
		self.assertEqual(total["driage"], 45.53)
		self.assertEqual(total["total_lot"], 319)

	def test_no_setup_or_lot_quantity(self):
		line = _line(frappe._dict(name="M3", company="X", type="RAW", lot_quantity=0), None, 100, {})
		self.assertEqual((line["cmr_due"], line["total_lot"], line["delivery_percent"]), (0, 0, 0))

	def test_season_of_dc(self):
		kharif_2025 = frappe._dict(crop_season="Kharif", year="2025")
		self.assertTrue(_in_season({"kms_year": "2025-26", "season": "KHARIF"}, kharif_2025))
		self.assertTrue(_in_season({"kms_year": "2025-26", "season": ""}, kharif_2025))
		self.assertFalse(_in_season({"kms_year": "2025-26", "season": "RABI"}, kharif_2025))
		self.assertFalse(_in_season({"kms_year": "2024-25", "season": "KHARIF"}, kharif_2025))
		self.assertFalse(_in_season({"kms_year": "", "season": "KHARIF"}, kharif_2025))

	def test_pending_lots(self):
		def rows(*cells):
			return [frappe._dict(name=f"PR-{i}", row_data=json.dumps(c), mill_id="M051007") for i, c in enumerate(cells)]

		records = {
			("SCMS", "Lot Search"): rows({"DC No.": "DCR051808", "Lot No.": "39", "Challan Status": "Accepted"}),
			("SCMS", "Transit Challan RRC"): rows(
				{"DC No": "DCR051808", "Lot No": "39", "Lot Challan Receipt status": "Accepted"},  # received
				{"DC No": "DCR051808", "Lot No": "40", "Lot Challan Receipt status": "Accepted"},  # pending
				{"DC No": "DCR051808", "Lot No": "41", "Lot Challan Receipt status": "Rejected"},
			),
			("DCRO", "DC Transit Challan"): rows(
				{"DC Order No": "DCF050748", "Lot No.": "32", "Pending At": "Approved"},
				{"DC Order No": "DCF050748", "Lot No.": "33", "Pending At": "Assitant Depot"},
				{"DC Order No": "DCF050748", "Lot No.": "33", "Pending At": "Assitant Depot"},  # read twice
				# Accepted Date (AC Note, or set by hand): not pending.
				{"DC Order No": "DCF050748", "Lot No.": "34", "Pending At": "Assitant Depot", "Accepted Date": "20-05-2026"},
			),
		}
		dcs = {"DCR051808": {"dc_no": "DCR051808"}}
		with patch(
			"ivri_od.procurement.report.dc_details.dc_details._records",
			side_effect=lambda site, section: records[(site, section)],
		):
			_add_pending(dcs)
		self.assertEqual(dcs["DCR051808"]["pending"], {"40"})
		# The pop-up rows: one challan row per pending lot, as read from the portal.
		self.assertEqual(dcs["DCR051808"]["pending_rows"]["40"]["Lot No"], "40")
		self.assertEqual(list(dcs["DCF050748"]["pending_rows"]), ["33"])
		self.assertEqual(dcs["DCF050748"]["pending"], {"33"})
		self.assertEqual(dcs["DCF050748"]["dc_type"], "FCI")

	def test_pending_is_shown_only(self):
		mill = frappe._dict(name="M1", company="SSPP BLD", type="BOILED", lot_quantity=290)
		lots = {"fci_issue": 90, "fci_delivery": 84, "rrc_issue": 40, "rrc_delivery": 39}
		without = _line(mill, BOILED, 78534.02, lots)
		with_pending = _line(mill, BOILED, 78534.02, {**lots, "fci_pending": 2, "rrc_pending": 1})
		self.assertEqual((with_pending["fci_pending"], with_pending["rrc_pending"]), (2, 1))
		for field in ("fci_delivery", "fci_balance", "rrc_balance", "total_delivery", "total_delivery_balance", "delivery_percent"):
			self.assertEqual(with_pending[field], without[field])

	def test_district_keeps_only_its_dcs(self):
		def dc(dc_no, kind, issued, delivered):
			return {"dc_no": dc_no, "mill_id": "M051007", "kms_year": "2025-26", "season": "", "dc_type": kind,
				"total_lots": issued, "lots": {str(i) for i in range(delivered)}}

		dcs = {
			"DCF-B1": dc("DCF-B1", "FCI", 10, 4),  # Balangir
			"DCR-B1": dc("DCR-B1", "RRC", 5, 5),  # Balangir
			"DCF-K1": dc("DCF-K1", "FCI", 7, 1),  # Koraput
			"DCF-X1": dc("DCF-X1", "FCI", 3, 0),  # no District in View DC
		}
		view_dc = [
			frappe._dict(row_data=json.dumps({"DC Code(RRC)": "DCF-B1", "District": "Balangir"})),
			frappe._dict(row_data=json.dumps({"DC Code(RRC)": "DCR-B1", "District": "BALANGIR "})),
			frappe._dict(row_data=json.dumps({"DC Code(RRC)": "DCF-K1", "District": "Koraput"})),
			frappe._dict(row_data=json.dumps({"DC Code(RRC)": "DCF-X1", "District": "No District Matched"})),
		]
		module = "ivri_od.procurement.report.dc_details.dc_details"
		kharif_2025 = frappe._dict(crop_season="Kharif", year="2025")
		with (
			patch(f"{module}._dcs_from_view_dc", side_effect=lambda: {k: dict(v) for k, v in dcs.items()}),
			patch(f"{module}._add_deliveries"),
			patch(f"{module}._add_pending"),
			patch(f"{module}._records", return_value=view_dc),
		):
			balangir, without = _dc_lots(kharif_2025, "Balangir")
			every, _none = _dc_lots(kharif_2025)
		mill = balangir["M051007"]
		self.assertEqual((mill["fci_issue"], mill["fci_delivery"], mill["rrc_issue"], mill["rrc_delivery"]), (10, 4, 5, 5))
		self.assertEqual(without, 1)  # DCF-X1
		self.assertEqual(every["M051007"]["fci_issue"], 20)  # every district: 10 + 7 + 3

	def test_pending_lots_pop_up(self):
		from ivri_od.procurement.report.dc_details import dc_details

		def dc(dc_no, mill, kind, pending):
			return {"dc_no": dc_no, "mill_id": mill, "dc_type": kind,
				"pending_rows": {lot: {"Lot No.": lot, "Pending At": "Assitant Depot", "Sl#": "1"} for lot in pending}}

		dcs = [dc("DCF-1", "M1", "FCI", ["10", "9"]), dc("DCF-2", "M2", "FCI", ["1"]), dc("DCR-1", "M1", "RRC", ["5"])]
		with (
			patch("frappe.db.get_value", return_value=frappe._dict(crop_season="Kharif", year="2025")),
			patch.object(dc_details, "_season_dcs", return_value=(dcs, 0)),
		):
			one = dc_details.get_pending_lots("Kharif 2025", "fci", mill="m1")
			every = dc_details.get_pending_lots("Kharif 2025", "FCI")
			rrc = dc_details.get_pending_lots("Kharif 2025", "rrc", mill="M1")
			self.assertRaises(frappe.ValidationError, dc_details.get_pending_lots, "Kharif 2025", "xyz")
		self.assertEqual([(lot["dc_no"], lot["lot_no"]) for lot in one["lots"]], [("DCF-1", "9"), ("DCF-1", "10")])
		self.assertEqual(len(every["lots"]), 3)  # Total line: every mill
		self.assertEqual([lot["lot_no"] for lot in rrc["lots"]], ["5"])
		self.assertNotIn("Sl#", one["lots"][0]["cells"])  # portal row number left out
		self.assertEqual(one["source"], "DCRO DC Transit Challan")

	def test_depot_name_from_dc_pdf_text(self):
		from ivri_od.procurement.portal_sync import _dc_depots_in

		# As read from the DC PDF: the line breaks differ from PDF to PDF ("Qtl1 RMC,...").
		one = "2.The delivery shall be made at the following depot :\nSlNo. Depot Name Depot Code No. of Lots Quantity in Qtl\n1 RMC,Kantabanji DG051601 1 290\n3.\nRRC FCI TOTAL"
		self.assertEqual(_dc_depots_in(one), "RMC,Kantabanji")
		joined = "SlNo. Depot Name Depot Code No. of Lots Quantity in Qtl1 RMC,Kantabanji DG051601 2 5803.\nRRC FCI TOTAL"
		self.assertEqual(_dc_depots_in(joined), "RMC,Kantabanji")
		two = "Quantity in Qtl1 SWC KANTABHANJI DW051602 1 2902 SWC BOLANGIR DW050101 1 290 3. RRC FCI TOTAL"
		self.assertEqual(_dc_depots_in(two), "SWC KANTABHANJI / SWC BOLANGIR")
		self.assertEqual(_dc_depots_in("no depot table"), "")

	def test_vr_pending(self):
		mill = frappe._dict(name="M1", company="SSPP BLD", type="BOILED", lot_quantity=290)
		lots = {"fci_issue": 90, "rrc_issue": 40, "requisition_qty": 43500}  # 43500 / 290 = 150 lots
		self.assertEqual(_line(mill, BOILED, 100, lots)["vr_pending"], 20)  # 150 - (90 + 40)
		self.assertEqual(_line(mill, BOILED, 100, {"fci_issue": 5})["vr_pending"], -5)  # no requisition read
		total = _total([_line(mill, BOILED, 100, lots), _line(mill, BOILED, 100, {"rrc_issue": 2})])
		self.assertEqual(total["vr_pending"], 18)  # 20 + (0 - 2)

	def test_requisition_qty_by_season_and_district(self):
		from ivri_od.procurement.report.dc_details import dc_details

		def row(kms, season, own, other="0.00", other2="0.00", status="Approved"):
			# Headers as read from DCRO Requisition for DC (Miller RQ PDS).
			return {
				"KMS Year": kms, "Season": season, "Requisition No.": "RQ1",
				"Quantity of Requistion (Own District) (in Qtl)": own,
				"Quantity of Requistion (Other District)KORAPUT (in Qtl)": other,
				"Quantity of Requistion (Other District) (in Qtl) 2": other2,
				"Status of Requisition": status,
			}

		rows = [
			row("2025-2026", "Kharif", "2,610.00", other="580.00", other2="290.00"),
			row("2025-2026", "Rabi", "290.00"),
			row("2024-2025", "Kharif", "290.00"),
			row("2025-2026", "Kharif", "290.00", status="Rejected"),
		]
		records = [frappe._dict(name=f"RQ-{i}", row_data=json.dumps(c), mill_id="M1") for i, c in enumerate(rows)]
		kharif_2025 = frappe._dict(crop_season="Kharif", year="2025")
		with (
			patch.object(dc_details, "_records", return_value=records),
			patch.object(dc_details, "mill_districts", return_value={"M1": "Balangir"}),
			patch.object(dc_details, "district_names", return_value={"balangir": "Balangir", "koraput": "Koraput"}),
		):
			self.assertEqual(dc_details._requisition_qty(kharif_2025), {"M1": 3480})  # every column
			self.assertEqual(dc_details._requisition_qty(kharif_2025, "Balangir"), {"M1": 2610})  # Own District
			self.assertEqual(dc_details._requisition_qty(kharif_2025, "Koraput"), {"M1": 580})  # named Other District
