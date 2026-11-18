# Copyright (c) 2026, Profezzo and contributors
"""RST form, Connections: its weighment and its GRN Note (government, rice or private).

RST name = RST No, so GRNs are matched on their RST No.
"""

from frappe import _


def get_data():
	return {
		"fieldname": "demo_rst_data",
		"non_standard_fieldnames": {"GRN Note": "rst_no"},
		"transactions": [
			{"label": _("Weighment"), "items": ["Weigh Bridge Measurement"]},
			{"label": _("GRN"), "items": ["GRN Note"]},
		],
	}
