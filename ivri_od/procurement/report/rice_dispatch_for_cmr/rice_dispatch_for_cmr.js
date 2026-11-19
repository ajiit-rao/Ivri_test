// Copyright (c) 2026, Profezzo and contributors

// Rice Dispatch for CMR: each rice dispatch to a depot with its weighment, the SCMS / DCRO row of
// the same lot, and download links for the Transit Challan and the AC Note saved from the portal.
const RICE_CMR_FILE_COLUMNS = ["transit_challan_file", "ac_note_file"];

frappe.query_reports["Rice Dispatch for CMR"] = {
	filters: [
		{ fieldname: "from_date", label: __("From Date"), fieldtype: "Date" },
		{ fieldname: "to_date", label: __("To Date"), fieldtype: "Date" },
		{ fieldname: "depot_name", label: __("Depot Name"), fieldtype: "Link", options: "Depo Master" },
		{ fieldname: "mill", label: __("Mill"), fieldtype: "Link", options: "Mill Master" },
		{
			fieldname: "portal_status",
			label: __("Portal Row"),
			fieldtype: "Select",
			options: ["", "Found", "Not Found"],
		},
	],
	formatter(value, row, column, data, default_formatter) {
		if (data && data.is_total) {
			return `<b>${default_formatter(value, row, column, data)}</b>`;
		}
		if (RICE_CMR_FILE_COLUMNS.includes(column.fieldname)) {
			if (!data || !data.portal) {
				return "";
			}
			return value
				? `<a href="${encodeURI(value)}" target="_blank" rel="noopener" download>${__("Download")}</a>`
				: `<span class="text-muted">${__("Not saved")}</span>`;
		}
		const text = default_formatter(value, row, column, data);
		if (column.fieldname === "match" && value) {
			const colour = { "Lot + Vehicle": "green", "Lot only": "orange", "Not found": "red" }[value] || "grey";
			return `<span class="indicator-pill ${colour}">${text}</span>`;
		}
		// Accepted at the depot less than weighed here: shown in red.
		if (column.fieldname === "difference" && data && flt(data.difference) < -0.0005) {
			return `<span style="color: var(--red-600)">${text}</span>`;
		}
		return text;
	},
};
