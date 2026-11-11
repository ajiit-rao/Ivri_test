// Copyright (c) 2026, Profezzo and contributors

// Filters, links and "Portal View" are shared: public/js/portal_detail_table.bundle.js.
// The saved DC document is linked as "Download_DC" on its RRC or FCI cell (in place of View_RRC / View_FCI).
// details: "Show Detail Rows (Lots)" lists the number of lots read from the DC page (grdDepotFCIbody / grdDepotRRCbody, td[4]).
// edit_district: the District (read from the DC PDF) can be set by hand; it is kept on later reads.
// dcro_filters: Mill Name, KMS Year, Season (Both / Kharif / Rabi), District, as on every DCRO
// Details report; then From Month - To Month (on the DC's Generated Date). All empty when the
// report opens (Season Both): every DC is shown until a filter is set.
frappe.query_reports["View DC from DCRO"] = ivri_od.portal.section_report_settings({
	file_link_text: "Download_DC",
	details: true,
	edit_district: true,
	dcro_filters: true,
	extra_filters: [
		{
			fieldname: "from_month",
			label: __("From Month"),
			fieldtype: "Date",
			description: __("On the Generated Date of the DC. Empty: all dates"),
		},
		{ fieldname: "to_month", label: __("To Month"), fieldtype: "Date" },
	],
});
