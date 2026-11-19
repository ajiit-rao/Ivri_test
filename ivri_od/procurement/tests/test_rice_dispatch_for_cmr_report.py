# Copyright (c) 2026, Profezzo and contributors

"""Rice Dispatch for CMR: how a weighment finds its SCMS / DCRO row (no database needed)."""

import json
import os
import unittest

from ivri_od.procurement.report.rice_dispatch_for_cmr import rice_dispatch_for_cmr as report

REPORT_JSON = os.path.join(
	os.path.dirname(__file__), "..", "report", "rice_dispatch_for_cmr", "rice_dispatch_for_cmr.json"
)


def _row(cells, receipt="", documents=None):
	return {"cells": cells, "receipt": receipt, "documents": documents or {}}


def _lookup(scms_challans=None, scms_lots=None, dcro_challans=None):
	lookup = report.PortalLookup.__new__(report.PortalLookup)  # no database: indexes given here
	lookup.scms_challans = scms_challans or {}
	lookup.scms_lots = scms_lots or {}
	lookup.dcro_challans = dcro_challans or {}
	return lookup


class TestKeys(unittest.TestCase):
	def test_lot_leading_zeros(self):
		self.assertEqual(report.lot_key(" 061 "), "61")
		self.assertEqual(report.lot_key("0"), "0")

	def test_vehicle_spaces_and_case(self):
		self.assertEqual(report.vehicle_key("od 03-y 5955"), "OD03Y5955")

	def test_depot_code_of_lot_search_cell(self):
		self.assertEqual(report.depot_code_of("DG051601-RMC,Kantabanji"), "DG051601")
		self.assertEqual(report.depot_code_of("dw051602"), "DW051602")

	def test_report_name(self):
		with open(REPORT_JSON) as f:
			meta = json.load(f)
		self.assertEqual(meta["name"], "Rice Dispatch for CMR")
		self.assertEqual(meta["report_name"], "Rice Dispatch for CMR")


class TestPickRow(unittest.TestCase):
	TRUCK_A = _row({"Vehicle No": "OD03Q8182", "Challan Date": "02/11/2026"}, "/a.pdf")
	TRUCK_B = _row({"Vehicle No": "OD03Q8384", "Challan Date": "01/11/2026"}, "/b.pdf")

	def test_two_trucks_same_lot_takes_own_vehicle(self):
		row, how = report.pick_row([self.TRUCK_A, self.TRUCK_B], "od03q8384", ["Vehicle No"], ["Challan Date"])
		self.assertEqual(row["receipt"], "/b.pdf")
		self.assertEqual(how, report.MATCH_VEHICLE)

	def test_other_vehicle_takes_newest(self):
		row, how = report.pick_row([self.TRUCK_B, self.TRUCK_A], "OD01X0001", ["Vehicle No"], ["Challan Date"])
		self.assertEqual(row["receipt"], "/a.pdf")
		self.assertEqual(how, report.MATCH_LOT)

	def test_nothing(self):
		self.assertEqual(report.pick_row([], "X", ["Vehicle No"], ["Challan Date"]), (None, report.MATCH_NONE))


class TestFind(unittest.TestCase):
	def test_dcro_row_and_documents(self):
		row = _row(
			{
				"DC Order No": "DCF051975",
				"Contract No.": "BLN/52/OSCSC/110",
				"Vechicle No.": "OR05AP4817",
				"No. of Bags(In kg.)": "580.00",
				"Acceptance Note No": "1746",
				"Accepted Date": "13-11-2026",
				"Net Weight": "289.03600",
				"Moisture": "13.70000",
				"Pending At": "Approved",
			},
			documents={"Details": "/details.pdf", "AC Note Doc": "/ac.pdf"},
		)
		found = _lookup(dcro_challans={("DW051602", "110"): [row]}).find("DW051602", "110", "OR05AP4817")
		self.assertEqual(found["portal"], "DCRO")
		self.assertEqual(found["match"], report.MATCH_VEHICLE)
		self.assertEqual(found["portal_bags"], 580)
		self.assertEqual(found["accepted_qty"], 289.036)
		self.assertEqual(found["transit_challan_file"], "/details.pdf")
		self.assertEqual(found["ac_note_file"], "/ac.pdf")

	def test_scms_challan_with_ac_note_of_same_dc(self):
		challan = _row(
			{"Challan No.": "0048", "DC No": "DCR051936", "Vehicle No": "OD03Q8182", "Bag": "580",
			 "Challan Date": "02/11/2026", "Lot Challan Receipt status": "Accepted"},
			"/challan.pdf",
		)
		other_dc = _row({"DC No.": "DCR000001", "A.C. Note No.": "0001"}, "/wrong.pdf")
		own_dc = _row(
			{"DC No.": "DCR051936", "A.C. Note No.": "0423", "Qty(In Qtl.)": "289.74000", "Receipt Date": "03/11/2026"},
			"/acnote.pdf",
		)
		lookup = _lookup(
			scms_challans={("DG051601", "45"): [challan]},
			scms_lots={("DG051601", "45"): [other_dc, own_dc]},
		)
		found = lookup.find("DG051601", "045", "OD03Q8182")
		self.assertEqual(found["portal"], "SCMS")
		self.assertEqual(found["challan_no"], "0048")
		self.assertEqual(found["ac_note_no"], "0423")
		self.assertEqual(found["accepted_qty"], 289.74)
		self.assertEqual(found["transit_challan_file"], "/challan.pdf")
		self.assertEqual(found["ac_note_file"], "/acnote.pdf")

	def test_row_of_another_mill_is_never_taken(self):
		other_mill = _row({"Vechicle No.": "OD01X0001"}, documents={"AC Note Doc": "/other.pdf"})
		other_mill["mill"] = "M050414"
		lookup = _lookup(dcro_challans={("DW051602", "48"): [other_mill]})
		self.assertEqual(lookup.find("DW051602", "48", "OD01X0001", "M051007")["match"], report.MATCH_NONE)
		# No mill on the weighment: the row is used.
		self.assertEqual(lookup.find("DW051602", "48", "OD01X0001", "")["portal"], "DCRO")
		# A row without a mill is kept.
		other_mill["mill"] = ""
		self.assertEqual(lookup.find("DW051602", "48", "OD01X0001", "M051007")["portal"], "DCRO")

	def test_not_found_and_no_lot(self):
		self.assertEqual(_lookup().find("DW051602", "48", "X")["match"], report.MATCH_NONE)
		self.assertEqual(_lookup().find("DW051602", "", "X")["match"], report.MATCH_NONE)


if __name__ == "__main__":
	unittest.main()
