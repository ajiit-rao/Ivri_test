# Copyright (c) 2026, Profezzo and contributors
# For license information, please see license.txt

"""Private Deal Report: every private deal (GRN Note of type "Private Deal", purchase or sale)
with its weighment (Weigh Bridge Measurement) and its GRN details on one row.
Cancelled GRNs are left out. Weights are in quintals (QT), as on the forms."""

import frappe
from frappe import _
from frappe.utils import flt

GRN_TYPE_PRIVATE = "Private Deal"
QT = 3  # decimals shown for quintals

# Columns added up in the total row (weights and bags; not moisture / dust).
TOTAL_FIELDS = (
	"bags",
	"load_weight",
	"tare_weight",
	"gross_weight",
	"gunny_weight",
	"deduction",
	"wbm_net_weight",
	"grn_net_weight",
	"difference",
	"jute_bags",
	"plastic_bags",
)


def execute(filters=None):
	filters = frappe._dict(filters or {})
	data = get_data(filters)
	if data:
		data.append(total_row(data))
	return get_columns(), data


def get_columns():
	def qt(fieldname, label, width=110):
		return {"fieldname": fieldname, "label": _(label), "fieldtype": "Float", "precision": QT, "width": width}

	return [
		# Deal
		{"fieldname": "grn", "label": _("GRN No"), "fieldtype": "Link", "options": "GRN Note", "width": 140},
		{"fieldname": "receipt_date", "label": _("GRN Date"), "fieldtype": "Date", "width": 100},
		{"fieldname": "transaction_type", "label": _("Purchase / Sale"), "fieldtype": "Data", "width": 100},
		{"fieldname": "deal_status", "label": _("Deal"), "fieldtype": "Data", "width": 190},
		{"fieldname": "party_name", "label": _("Party"), "fieldtype": "Data", "width": 180},
		{"fieldname": "mill_name", "label": _("Mill Name"), "fieldtype": "Data", "width": 220},
		{"fieldname": "commodity", "label": _("Commodity"), "fieldtype": "Data", "width": 150},
		{"fieldname": "vehicle_no", "label": _("Vehicle No"), "fieldtype": "Data", "width": 110},
		{"fieldname": "rst_no", "label": _("RST No"), "fieldtype": "Data", "width": 80},
		# Weighment
		{
			"fieldname": "weighment",
			"label": _("Weighment"),
			"fieldtype": "Link",
			"options": "Weigh Bridge Measurement",
			"width": 140,
		},
		{"fieldname": "weighment_date", "label": _("Weighment Date"), "fieldtype": "Datetime", "width": 150},
		{"fieldname": "bags", "label": _("Bags"), "fieldtype": "Int", "width": 70},
		qt("load_weight", "Load Weight (QT)"),
		qt("tare_weight", "Tare Weight (QT)"),
		qt("gross_weight", "Gross Weight (QT)"),
		qt("gunny_weight", "Gunny Weight (QT)"),
		qt("deduction", "Deduction (QT)"),
		qt("wbm_net_weight", "Weighment Net (QT)", 130),
		# GRN
		qt("grn_net_weight", "GRN Net (QT)"),
		qt("difference", "Difference (QT)"),
		{"fieldname": "jute_bags", "label": _("Jute Bags"), "fieldtype": "Int", "width": 80},
		{"fieldname": "plastic_bags", "label": _("Plastic Bags"), "fieldtype": "Int", "width": 90},
		{"fieldname": "moisture", "label": _("Moisture %"), "fieldtype": "Float", "precision": 2, "width": 90},
		{"fieldname": "dust", "label": _("Dust %"), "fieldtype": "Float", "precision": 2, "width": 80},
		{"fieldname": "qc_decision", "label": _("QC Decision"), "fieldtype": "Data", "width": 110},
		{"fieldname": "grn_status", "label": _("GRN Status"), "fieldtype": "Data", "width": 90},
	]


def get_data(filters):
	grn = frappe.qb.DocType("GRN Note")
	wbm = frappe.qb.DocType("Weigh Bridge Measurement")
	query = (
		frappe.qb.from_(grn)
		.left_join(wbm)
		.on(wbm.name == grn.weigh_bridge_measurement)
		.select(
			grn.name.as_("grn"),
			grn.receipt_date,
			grn.transaction_type,
			grn.deal_status,
			grn.party_name,
			grn.mill_name,
			wbm.mill_name.as_("wbm_mill_name"),
			grn.commodity,
			grn.vehicle_no,
			grn.rst_no,
			grn.docstatus,
			grn.net_weight.as_("grn_net_weight"),
			grn.jute_bags,
			grn.plastic_bags,
			grn.moisture,
			grn.dust,
			grn.qc_decision,
			wbm.name.as_("weighment"),
			wbm.date.as_("weighment_date"),
			wbm.total_bags.as_("bags"),
			wbm.load_weight,
			wbm.tare_weight,
			wbm.gross_weight,
			wbm.gunny_weight,
			wbm.deduction,
			wbm.net_weight.as_("wbm_net_weight"),
		)
		.where(grn.grn_type == GRN_TYPE_PRIVATE)
		.where(grn.docstatus < 2)
		.orderby(grn.receipt_date)
		.orderby(grn.name)
	)
	if filters.from_date:
		query = query.where(grn.receipt_date >= filters.from_date)
	if filters.to_date:
		query = query.where(grn.receipt_date <= filters.to_date)
	if filters.transaction_type:
		query = query.where(grn.transaction_type == filters.transaction_type)
	if filters.party_name:
		query = query.where(grn.party_name.like(f"%{filters.party_name.strip()}%"))
	if filters.commodity:
		query = query.where(grn.commodity.like(f"%{filters.commodity.strip()}%"))
	if filters.mill:
		query = query.where(wbm.mill == filters.mill)
	if filters.grn_status:
		query = query.where(grn.docstatus == (1 if filters.grn_status == "Submitted" else 0))

	rows = query.run(as_dict=True)
	for row in rows:
		row.grn_status = _("Submitted") if row.docstatus == 1 else _("Draft")
		# Mill: RST Mill No -> weighment -> GRN; the weighment's when the GRN is not saved again yet.
		row.mill_name = row.mill_name or row.wbm_mill_name or ""
		# Difference = GRN net - weighment net; blank when there is no weighment.
		row.difference = flt(row.grn_net_weight) - flt(row.wbm_net_weight) if row.weighment else None
	return rows


def total_row(rows):
	total = {"grn": "", "party_name": _("Total ({0} deals)").format(len(rows)), "bold": 1}
	for field in TOTAL_FIELDS:
		total[field] = sum(flt(r.get(field)) for r in rows)
	return total
