"""The Rice Dispatch report is now called Rice Dispatch for CMR (one row per dispatch, with the
SCMS / DCRO row and documents of the lot).

A standard report's name is its key, so the old definition is dropped once the new one exists (it is only
the report's definition: no weighment data is involved). Workspace links to it go with it; the Procurement
workspace is rebuilt after migrate with the new name.
"""

import frappe

OLD_NAME = "Rice Dispatch"
NEW_NAME = "Rice Dispatch for CMR"


def execute():
	frappe.reload_doc("procurement", "report", "rice_dispatch_for_cmr")
	if not frappe.db.exists("Report", NEW_NAME):
		return  # keep the old definition until the new one is in place
	if frappe.db.exists("Report", OLD_NAME):
		frappe.db.delete("Workspace Link", {"link_type": "Report", "link_to": OLD_NAME})
		frappe.db.delete("Workspace Shortcut", {"type": "Report", "link_to": OLD_NAME})
		frappe.db.delete("Has Role", {"parent": OLD_NAME, "parenttype": "Report"})
		frappe.db.delete("Report", {"name": OLD_NAME})
	frappe.clear_cache()
