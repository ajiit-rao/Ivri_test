// Copyright (c) 2026, Profezzo and contributors

frappe.query_reports["Rice Stock Report"] = {
	filters: [
		{
			fieldname: "mill",
			label: __("Mill Name"),
			fieldtype: "Link",
			options: "Mill Master",
			reqd: 1,
			description: __("Rice percentage from Rice Delivery Setup by the mill's Type (Raw / Boiled)"),
			on_change: (report) => {
				// The mill's company is printed in the heading.
				const mill = report.get_filter_value("mill");
				const company_of_mill = mill
					? frappe.db.get_value("Mill Master", mill, "company").then((r) => r.message?.company || "")
					: Promise.resolve("");
				company_of_mill.then((company) => {
					// Setting the same company again does not refresh the report, so refresh here.
					if (company === (report.get_filter_value("company") || "")) {
						report.refresh();
					} else {
						report.set_filter_value("company", company);
					}
				});
			},
		},
		{
			fieldname: "kms_year",
			label: __("KMS Year"),
			fieldtype: "Select",
			reqd: 1,
			description: __("Kharif and Rabi of the year"),
		},
		{
			fieldname: "district",
			label: __("District"),
			fieldtype: "Link",
			options: "District Master",
			get_query: () => ({ filters: { is_active: 1 } }),
			description: __("Only this district's DCs (District in View DC from DCRO). Empty: every district."),
		},
		{
			// No From / To Month: the months come from the season (Season Master Start - End Date,
			// else the first to the last month with data of the chosen season).
			fieldname: "season",
			label: __("Season"),
			fieldtype: "Select",
			options: "Both\nKharif\nRabi",
			default: "Both",
			reqd: 1,
			description: __("Both: Kharif and Rabi of the KMS Year. Months are shown automatically"),
		},
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			hidden: 1,
		},
	],
	onload(report) {
		// Print, Download > PDF (same statement layout, rice_stock_report.html, A4 landscape) and Download > Excel.
		ivri_od.report_print.add_buttons(report);

		// KMS Years from Season Master, newest first ("25-26" = Kharif 2025 and Rabi 2025).
		return frappe
			.call(
				"ivri_od.procurement.report.stock_account_for_paddy.stock_account_for_paddy.get_kms_years"
			)
			.then((r) => {
				const years = r.message || [];
				const filter = report.get_filter("kms_year");
				filter.df.options = years;
				filter.refresh();
				if (!years.includes(filter.get_value())) {
					return filter.set_value(years[0] || "");
				}
			});
	},
	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		return data && data.bold ? `<b>${value}</b>` : value;
	},
};
