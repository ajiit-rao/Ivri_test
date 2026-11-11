// Copyright (c) 2026, Profezzo and contributors

// Filters, links and "Portal View" are shared: public/js/portal_detail_table.bundle.js.
// dcro_filters: Mill Name, KMS Year, Season (Both / Kharif / Rabi), District, as on every DCRO Details report.
frappe.query_reports["Requisition for DC from DCRO"] = ivri_od.portal.section_report_settings({ dcro_filters: true });
