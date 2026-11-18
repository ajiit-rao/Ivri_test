# Copyright (c) 2026, Profezzo and Contributors
# See license.txt

from frappe.tests.utils import FrappeTestCase


class TestGRNNote(FrappeTestCase):
	pass


from unittest import TestCase as _TestCase
from unittest.mock import patch as _patch


class TestGRNTypeNoDB(_TestCase):
	"""One GRN Note for every weighment; GRN Type and the rice / private values come from the weighment."""

	def _grn(self, **values):
		from ivri_od.procurement.doctype.grn_note.grn_note import GRNNote

		doc = GRNNote.__new__(GRNNote)
		for key, value in {"is_rice_dispatch": 0, "is_local_procurement": 0, "weigh_bridge_measurement": "WBM-1",
				"mill_name": "TP MILL", "commodity": "Paddy", "transaction_type": "", "deal_status": "",
				"local_procurement_note": "", **values}.items():
			doc.__dict__[key] = value
		return doc

	def _sync(self, doc, wbm):
		import frappe

		with _patch("ivri_od.procurement.doctype.grn_note.grn_note.frappe.db.get_value", return_value=frappe._dict(wbm)):
			doc.sync_grn_type_and_trade_fields()
		return doc

	def test_private_deal(self):
		doc = self._sync(self._grn(is_local_procurement=1), {"mill_name": "Shree Mill", "commodity": "BRAN",
			"transaction_type": "SALE", "tp_status": "Local BRAN Sale"})
		self.assertEqual((doc.grn_type, doc.transaction_type, doc.deal_status, doc.commodity, doc.mill_name),
			("Private Deal", "Sale", "Local BRAN Sale", "BRAN", "Shree Mill"))
		self.assertEqual(doc.local_procurement_note, "Local BRAN Sale")

	def test_rice(self):
		doc = self._sync(self._grn(is_rice_dispatch=1, is_local_procurement=1), {"mill_name": "SSSB",
			"commodity": "CMR RICE", "transaction_type": "SALE", "tp_status": "Rice Dispatch"})
		self.assertEqual((doc.grn_type, doc.is_local_procurement, doc.mill_name, doc.transaction_type),
			("Rice Delivery to Depo", 0, "SSSB", ""))

	def test_government_keeps_transit_pass_mill(self):
		doc = self._grn()
		doc.sync_grn_type_and_trade_fields()
		self.assertEqual((doc.grn_type, doc.mill_name, doc.transaction_type), ("Government Paddy", "TP MILL", ""))
