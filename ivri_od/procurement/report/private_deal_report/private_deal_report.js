// Copyright (c) 2026, Profezzo and contributors

// Private Deal Report: each private deal (purchase / sale) with its weighment and GRN details.
frappe.query_reports["Private Deal Report"] = {
	filters: [
		{ fieldname: "from_date", label: __("From Date"), fieldtype: "Date" },
		{ fieldname: "to_date", label: __("To Date"), fieldtype: "Date" },
		{
			fieldname: "transaction_type",
			label: __("Purchase / Sale"),
			fieldtype: "Select",
			options: ["", "Purchase", "Sale"],
		},
		{ fieldname: "party_name", label: __("Party"), fieldtype: "Data" },
		{ fieldname: "commodity", label: __("Commodity"), fieldtype: "Data" },
		{ fieldname: "mill", label: __("Mill"), fieldtype: "Link", options: "Mill Master" },
		{ fieldname: "grn_status", label: __("GRN Status"), fieldtype: "Select", options: ["", "Draft", "Submitted"] },
	],
	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (data && data.bold) {
			return `<b>${value}</b>`;
		}
		// A GRN that does not match its weighment is shown in red.
		if (column.fieldname === "difference" && data && Math.abs(data.difference || 0) > 0.0005) {
			return `<span style="color: var(--red-600)">${value}</span>`;
		}
		return value;
	},
};
