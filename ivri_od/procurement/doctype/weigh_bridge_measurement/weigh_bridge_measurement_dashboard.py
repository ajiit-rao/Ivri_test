# Copyright (c) 2026, Profezzo and contributors
"""Weigh Bridge form, Connections: its GRN Note (government, rice or private)."""

from frappe import _


def get_data():
	return {
		"fieldname": "weigh_bridge_measurement",
		"transactions": [
			{"label": _("GRN"), "items": ["GRN Note"]},
		],
	}
