# Copyright (c) 2026, Profezzo and contributors
# For license information, please see license.txt

"""Other TPs in one RST: weighment weights and checks, split weighment weights, GRN and the Mandi Book line.

Example used: RST 1201 weighs 250 QT net under TP 46 and also carries 80 QT of TP 51.
Truck weighment Net 170 (RST Net 250); split weighment of TP 51: the truck's Load and Tare, Net 80 less
its own Deduction.
"""

import unittest
from unittest.mock import patch

import frappe
from frappe.utils import flt

from ivri_od.procurement import other_tp
from ivri_od.procurement.report.mandi_book import mandi_book

OTHER_TP = "ivri_od.procurement.other_tp"
OWN_KEY = "M1-PPC(S1)-K25-TP46"
TP_51 = {"pass_unique_key": "M1-PPC(S1)-K25-TP51", "miller": "Mill One"}


def _wbm(rows, rst_net=250.0, key=OWN_KEY, tp_no="46"):
	"""An unsaved truck weighment in memory (is_new, so no GRN lookup)."""
	doc = frappe.new_doc("Weigh Bridge Measurement")
	doc.pass_unique_key = key
	doc.transit_pass_no = tp_no
	doc.pacs_name = "PPC"
	doc.rst_no = "1201"
	doc.net_weight = rst_net
	for row in rows:
		doc.append("other_tp_details", row)
	other_tp.adjust_weights_for_other_tps(doc)  # as at the end of _update_weights
	return doc


def _validate(doc, found=TP_51, mill="M1"):
	with (
		patch(f"{OTHER_TP}.resolve_ppc_master_name", return_value="S1"),
		patch(f"{OTHER_TP}.get_transit_pass_for_ppc_and_tp_no", return_value=found),
		patch(f"{OTHER_TP}.resolve_mill_master_name", return_value=mill),
	):
		other_tp.validate_other_tps(doc)


class TestTruckWeighment(unittest.TestCase):
	def test_net_is_rst_net_less_other_tps(self):
		doc = _wbm([{"transit_pass_no": "51", "qty": 80}])
		self.assertEqual(flt(doc.rst_net_weight, 3), 250)
		self.assertEqual(flt(doc.other_tp_qty, 3), 80)
		self.assertEqual(flt(doc.net_weight, 3), 170)

	def test_without_other_tps_net_is_the_truck(self):
		doc = _wbm([])
		self.assertEqual(flt(doc.net_weight, 3), 250)
		self.assertEqual(flt(doc.rst_net_weight, 3), 250)

	def test_row_gets_tp_key_ppc_and_mill(self):
		doc = _wbm([{"transit_pass_no": "51", "qty": 80}])
		_validate(doc)
		row = doc.other_tp_details[0]
		self.assertEqual(row.pass_unique_key, TP_51["pass_unique_key"])
		self.assertEqual(row.ppc_name, "S1")
		self.assertEqual(row.mill_no, "M1")

	def test_empty_rows_are_dropped(self):
		doc = _wbm([{"transit_pass_no": "", "qty": 0}, {"transit_pass_no": "51", "qty": 80}])
		_validate(doc)
		self.assertEqual(len(doc.other_tp_details), 1)

	def test_own_tp_is_refused(self):
		with self.assertRaises(frappe.ValidationError):
			_validate(_wbm([{"transit_pass_no": "46", "qty": 10}]), found={"pass_unique_key": OWN_KEY})

	def test_unknown_tp_is_refused(self):
		with self.assertRaises(frappe.ValidationError):
			_validate(_wbm([{"transit_pass_no": "99", "qty": 10}]), found=None)

	def test_wrong_mill_is_refused(self):
		with self.assertRaises(frappe.ValidationError):
			_validate(_wbm([{"transit_pass_no": "51", "mill_no": "M9", "qty": 10}]))

	def test_qty_must_be_less_than_rst_net(self):
		with self.assertRaises(frappe.ValidationError):
			_validate(_wbm([{"transit_pass_no": "51", "qty": 250}]))

	def test_qty_must_be_given(self):
		with self.assertRaises(frappe.ValidationError):
			_validate(_wbm([{"transit_pass_no": "51", "qty": 0.0001}, {"transit_pass_no": "52", "qty": -1}]))

	def test_same_tp_twice_is_refused(self):
		with self.assertRaises(frappe.ValidationError):
			_validate(_wbm([{"transit_pass_no": "51", "qty": 10}, {"transit_pass_no": "51", "qty": 5}]))

	def test_only_under_a_transit_pass(self):
		with self.assertRaises(frappe.ValidationError):
			_validate(_wbm([{"transit_pass_no": "51", "qty": 10}], key=""))


TRUCK = frappe._dict(
	load_weight=400, tare_weight=140, gross_weight=260, gunny_weight=5, deduction=5, net_weight=170,
	rst_net_weight=250, total_bags=500, no_of_bags=500, quality_test="Accepted",
)


def _split(deduction=None, truck=TRUCK):
	child = frappe.new_doc("Weigh Bridge Measurement")
	child.split_from_weighment = "WBM-TRUCK"
	child.split_qty = 80
	child.deduction = deduction
	with patch(f"{OTHER_TP}.frappe.db.get_value", return_value=truck):
		other_tp._copy_split_weights(child)
	return child


class TestSplitWeighment(unittest.TestCase):
	def test_truck_load_and_tare_and_net_is_its_qty(self):
		child = _split()
		self.assertEqual(flt(child.load_weight, 3), 400)
		self.assertEqual(flt(child.tare_weight, 3), 140)
		self.assertEqual(flt(child.gross_weight, 3), 260)
		self.assertEqual(flt(child.rst_net_weight, 3), 250)
		self.assertEqual(flt(child.deduction, 3), 0)  # not the truck's 5
		self.assertEqual(flt(child.net_weight, 3), 80)
		self.assertEqual(child.total_bags, 500)

	def test_own_deduction_lowers_its_net(self):
		self.assertEqual(flt(_split(deduction=2).net_weight, 3), 78)

	def test_deduction_must_be_less_than_qty(self):
		with self.assertRaises(frappe.ValidationError):
			_split(deduction=80)
		with self.assertRaises(frappe.ValidationError):
			_split(deduction=-1)

	def test_rejected_truck_gives_zero(self):
		self.assertEqual(flt(_split(truck=frappe._dict(TRUCK, quality_test="Rejected")).net_weight), 0)

	def test_split_weighment_cannot_have_other_tps(self):
		doc = _wbm([{"transit_pass_no": "52", "qty": 5}])
		doc.split_from_weighment = "WBM-TRUCK"
		with self.assertRaises(frappe.ValidationError):
			_validate(doc)


class TestMandiBookLine(unittest.TestCase):
	def _line(self, gross, gunny, deduction, net, other_tp_qty, wbm=None):
		doc = frappe._dict(
			name="GRN-1", grn_no="GRN-1", rst_no="1201", weigh_bridge_measurement="WBM-1" if wbm else "",
			vehicle_no="CG04AB1234", gross_vehicle_weight=gross + 140, tare_weight=140, gross_weight=gross,
			gunny_weight=gunny, deduction=deduction, net_weight=net, gunny_type="Gunny Gross",
			other_tp_qty=other_tp_qty,
		)
		wbms = {"WBM-1": frappe._dict(wbm, name="WBM-1")} if wbm else {}
		return mandi_book._rst_lines([doc], wbms, {})[0]

	def test_truck_grn_counts_only_its_share(self):
		line = self._line(260, 5, 5, 170, 80)
		self.assertAlmostEqual(line["gross_weight"] - line["gunny_weight"] - line["deduction"], 170, places=3)
		self.assertEqual(flt(line["net_weight"], 3), 170)

	def test_split_grn_gets_its_share_of_the_truck(self):
		# Split weighment of 80 QT with its own Deduction 2: the truck's weights, Net 78.
		wbm = dict(
			load_weight=400, tare_weight=140, gross_weight=260, gunny_weight=5, deduction=2, net_weight=78,
			rst_net_weight=250, split_from_weighment="WBM-TRUCK", split_qty=80,
		)
		line = self._line(260, 5, 2, 78, 170, wbm=wbm)
		self.assertEqual(flt(line["gross_weight"], 3), 83.2)  # 260 x 80/250
		self.assertEqual(flt(line["net_weight"], 3), 78)
		self.assertAlmostEqual(line["gross_weight"] - line["gunny_weight"] - line["deduction"], 78, places=3)

	def test_line_unchanged_without_other_tps(self):
		line = self._line(260, 5, 5, 250, 0)
		self.assertEqual(flt(line["gross_weight"], 3), 260)
		self.assertIsNone(line["other_tp_qty"])
