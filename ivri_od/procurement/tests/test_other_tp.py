# Copyright (c) 2026, Profezzo and contributors
# For license information, please see license.txt

"""Other TPs in one RST: weighment checks, GRN Net Weight and the Mandi Book line.

Example used: RST 1201 weighs 250 QT net under TP 46 and also carries 80 QT of TP 51 -> GRN 170 QT.
"""

import unittest
from unittest.mock import patch

import frappe
from frappe.utils import flt

from ivri_od.procurement.other_tp import apply_other_tps_to_grn, validate_other_tps
from ivri_od.procurement.report.mandi_book import mandi_book

OTHER_TP = "ivri_od.procurement.other_tp"


def _wbm(rows, net=250.0, key="46-PPC-2026", tp_no="46"):
	"""An unsaved weighment in memory (is_new, so no GRN lookup)."""
	doc = frappe.new_doc("Weigh Bridge Measurement")
	doc.pass_unique_key = key
	doc.transit_pass_no = tp_no
	doc.rst_no = "1201"
	doc.net_weight = net
	for row in rows:
		doc.append("other_tp_details", row)
	return doc


class TestValidateOtherTPs(unittest.TestCase):
	def test_total_is_set(self):
		doc = _wbm([{"transit_pass_no": "51", "qty": 80}, {"transit_pass_no": "52", "qty": 20.5}])
		validate_other_tps(doc)
		self.assertEqual(flt(doc.other_tp_qty, 3), 100.5)

	def test_empty_rows_are_dropped(self):
		doc = _wbm([{"transit_pass_no": "", "qty": 0}, {"transit_pass_no": "51", "qty": 80}])
		validate_other_tps(doc)
		self.assertEqual(len(doc.other_tp_details), 1)
		self.assertEqual(doc.other_tp_details[0].idx, 1)

	def test_no_rows_means_zero(self):
		doc = _wbm([])
		validate_other_tps(doc)
		self.assertEqual(flt(doc.other_tp_qty), 0)

	def test_own_tp_is_refused(self):
		with self.assertRaises(frappe.ValidationError):
			validate_other_tps(_wbm([{"transit_pass_no": "46", "qty": 10}]))

	def test_qty_must_be_less_than_rst_net(self):
		with self.assertRaises(frappe.ValidationError):
			validate_other_tps(_wbm([{"transit_pass_no": "51", "qty": 250}]))

	def test_qty_must_be_given(self):
		with self.assertRaises(frappe.ValidationError):
			validate_other_tps(_wbm([{"transit_pass_no": "51", "qty": 0}]))

	def test_same_tp_twice_is_refused(self):
		with self.assertRaises(frappe.ValidationError):
			validate_other_tps(_wbm([{"transit_pass_no": "51", "qty": 10}, {"transit_pass_no": "51", "qty": 5}]))

	def test_only_under_a_transit_pass(self):
		with self.assertRaises(frappe.ValidationError):
			validate_other_tps(_wbm([{"transit_pass_no": "51", "qty": 10}], key=""))


class TestGRNNetWeight(unittest.TestCase):
	def test_grn_net_is_rst_net_less_other_tps(self):
		grn = frappe.new_doc("GRN Note")
		rows = [frappe._dict(transit_pass_no="51", ppc_name="", mill_no="", qty=80)]
		with patch(f"{OTHER_TP}.frappe.get_all", return_value=rows):
			apply_other_tps_to_grn(grn, "WBM-X", 250)
		self.assertEqual(flt(grn.rst_net_weight, 3), 250)
		self.assertEqual(flt(grn.other_tp_qty, 3), 80)
		self.assertEqual(flt(grn.net_weight, 3), 170)
		self.assertEqual(grn.other_tp_details[0].transit_pass_no, "51")

	def test_without_other_tps_net_is_unchanged(self):
		grn = frappe.new_doc("GRN Note")
		with patch(f"{OTHER_TP}.frappe.get_all", return_value=[]):
			apply_other_tps_to_grn(grn, "WBM-X", 250)
		self.assertEqual(flt(grn.net_weight, 3), 250)
		self.assertEqual(flt(grn.other_tp_qty), 0)


class TestMandiBookLine(unittest.TestCase):
	def _line(self, other_tp_qty):
		doc = frappe._dict(
			name="GRN-1", grn_no="GRN-1", rst_no="1201", weigh_bridge_measurement="", vehicle_no="CG04AB1234",
			gross_vehicle_weight=400, tare_weight=140, gross_weight=260, gunny_weight=5, deduction=5,
			net_weight=250 - other_tp_qty, gunny_type="Gunny Gross", other_tp_qty=other_tp_qty,
		)
		return mandi_book._rst_lines([doc], {}, {})[0]

	def test_received_is_reduced_by_other_tps(self):
		line = self._line(80)
		# Mandi Book counts gross - gunny - deduction: it must be this TP's 170 QT only.
		self.assertAlmostEqual(line["gross_weight"] - line["gunny_weight"] - line["deduction"], 170, places=3)
		self.assertEqual(flt(line["net_weight"], 3), 170)
		self.assertEqual(line["other_tp_qty"], 80)

	def test_line_unchanged_without_other_tps(self):
		line = self._line(0)
		self.assertEqual(flt(line["gross_weight"], 3), 260)
		self.assertAlmostEqual(line["gross_weight"] - line["gunny_weight"] - line["deduction"], 250, places=3)
		self.assertIsNone(line["other_tp_qty"])
