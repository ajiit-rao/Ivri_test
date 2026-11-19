"""The Rice Dispatch Summary report was renamed Rice Dispatch (later Rice Dispatch for CMR, see
rename_rice_dispatch_to_cmr_report, which loads the new report).

A standard report's name is its key, so the old definition is dropped (it is only the report's
definition: no weighment data, filters or saved lists are involved).
"""

import frappe

OLD_NAME = "Rice Dispatch Summary"


def execute():
	if frappe.db.exists("Report", OLD_NAME):
		frappe.db.delete("Has Role", {"parent": OLD_NAME, "parenttype": "Report"})
		frappe.db.delete("Report", {"name": OLD_NAME})
	frappe.clear_cache()
