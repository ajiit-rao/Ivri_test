// Copyright (c) 2026, Profezzo and contributors

// KMS Years from Season Master, newest first ("24-25" = 01-11-2024 to 31-10-2025).
function load_custody_kms_years(report) {
	return frappe
		.call("ivri_od.procurement.report.stock_account_for_paddy.stock_account_for_paddy.get_kms_years")
		.then((r) => {
			const years = r.message || [];
			const filter = report.get_filter("kms_year");
			filter.df.options = years;
			filter.refresh();
			if (!years.includes(filter.get_value())) {
				return filter.set_value(years[0] || "");
			}
		});
}

frappe.query_reports["Joint Custody and Maintenance Charge Report"] = {
	filters: [
		{
			fieldname: "mill",
			label: __("Miller Name"),
			fieldtype: "Link",
			options: "Mill Master",
			reqd: 1,
			on_change: (report) => {
				// The mill's District and name (printed in the heading) come from Mill Master.
				const mill = report.get_filter_value("mill");
				if (!mill) {
					report.set_filter_value("miller_name", "");
					return;
				}
				frappe.db.get_value("Mill Master", mill, ["company", "district"]).then((r) => {
					const values = r.message || {};
					report.set_filter_value({
						miller_name: values.company || mill,
						district: values.district || report.get_filter_value("district") || "",
					});
				});
			},
		},
		{
			fieldname: "kms_year",
			label: __("KMS Year"),
			fieldtype: "Select",
			reqd: 1,
			description: __("1 Nov to 31 Oct, e.g. 24-25 = 01-11-2024 to 31-10-2025"),
		},
		{
			// No From / To Month: the months come from the season (Season Master Start - End Date,
			// else the first to the last month with data).
			fieldname: "season",
			label: __("Season"),
			fieldtype: "Select",
			options: "Both\nKharif\nRabi",
			default: "Both",
			reqd: 1,
			description: __("Both: Kharif and Rabi of the KMS Year. Months are shown automatically"),
		},
		{
			fieldname: "district",
			label: __("District"),
			fieldtype: "Link",
			options: "District Master",
			reqd: 1,
		},
		{
			fieldname: "miller_name",
			label: __("Miller Name"),
			fieldtype: "Data",
			hidden: 1,
		},
	],
	onload(report) {
		// Print, Download > PDF (joint_custody_and_maintenance_charge_report.html, A4 landscape) and Excel.
		ivri_od.report_print.add_buttons(report);
		return load_custody_kms_years(report);
	},
	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		return data && data.bold ? `<b>${value}</b>` : value;
	},
};
