// Copyright (c) 2026, Profezzo and contributors
// For license information, please see license.txt

// List view settings must live in this *_list.js file: Frappe loads the form script only after a form
// of this DocType has been opened, so settings kept there are missing after a page refresh.
// Status "Rice Dispatch" (Party Name is a depo) is shown to staff as "Rice Delivery to Depo", or
// "Lot No is empty" when TP No (the Lot No for a depo) is blank. Only the display changes: the saved
// value stays "Rice Dispatch" (weighment, report and filters use it).
frappe.listview_settings["RST Details"] = {
	add_fields: ["tp_no", "tp_status"],
	formatters: {
		// Depo RST: its number is a Lot No, shown in the Lot No column, so TP No stays empty.
		tp_no(value, df, doc) {
			if (doc?.tp_status === "Rice Dispatch") {
				return "";
			}
			return frappe.utils.escape_html(value || "");
		},
		tp_status(value, df, doc) {
			if (value !== "Rice Dispatch") {
				return frappe.utils.escape_html(__(value || ""));
			}
			if (!(doc?.tp_no || "").trim()) {
				return `<span class="text-danger">${frappe.utils.escape_html(__("Lot No is empty"))}</span>`;
			}
			return frappe.utils.escape_html(__("Rice Delivery to Depo"));
		},
	},
	onload(listview) {
		// Open with no filter: Frappe remembers the filters used last time, which hid data from staff.
		// A link with filters in its address (route options) is left alone.
		if (!Object.keys(frappe.route_options || {}).length && listview.filter_area) {
			listview.filter_area.clear();
		}
		add_rst_status_filter(listview);
	},
};

// Status filter: the same texts the Status column shows. A depo RST is saved as "Rice Dispatch"; it shows
// as "Rice Delivery to Depo", or "Lot No is empty" when its Lot No is blank, so those two filter on Lot No too.
const RST_STATUS_FILTERS = {
	"TP Received": [["tp_status", "=", "TP Received"]],
	"TP No Not Received": [["tp_status", "=", "TP No Not Received"]],
	"PPC Mismatch": [["tp_status", "=", "PPC Mismatch"]],
	"Invalid TP No": [["tp_status", "=", "Invalid TP No"]],
	// Private deals: status is "Local {Commodity} {Transaction Type}", e.g. "Local BRAN Sale".
	"Local (Private) - All": [["tp_status", "like", "Local%"]],
	"Local - Purchase": [["tp_status", "like", "Local% Purchase"]],
	"Local - Sale": [["tp_status", "like", "Local% Sale"]],
	"Rice Delivery to Depo": [
		["tp_status", "=", "Rice Dispatch"],
		["lot_no", "is", "set"],
	],
	"Lot No is empty": [
		["tp_status", "=", "Rice Dispatch"],
		["lot_no", "is", "not set"],
	],
};

function add_rst_status_filter(listview) {
	if (!listview.page || listview.rst_status_filter) {
		return;
	}
	listview.rst_status_filter = listview.page.add_field({
		fieldname: "rst_status_filter",
		label: __("Status"),
		fieldtype: "Select",
		options: ["", ...Object.keys(RST_STATUS_FILTERS)].map((label) => ({ label: __(label), value: label })),
		change() {
			const chosen = RST_STATUS_FILTERS[this.get_value()] || [];
			const area = listview.filter_area;
			// Drop the previous Status choice (and its Lot No part), then apply the new one.
			const old = area.get().filter((f) => f[1] === "tp_status" || f[1] === "lot_no");
			old.forEach((f) => area.filter_list.get_filter(f[1])?.remove());
			if (chosen.length) {
				area.add(chosen.map((f) => ["RST Details", ...f]));
			} else {
				area.filter_list.apply();
			}
		},
	});
	// Frappe sends every field in page.fields_dict to the query as "fieldname = value". This drop-down is
	// not a column (it applies the tp_status / lot_no filters above), so keep it out of that list.
	delete listview.page.fields_dict.rst_status_filter;
}
