// Copyright (c) 2026, Profezzo and contributors
// For license information, please see license.txt

// List view settings must live in this *_list.js file: Frappe loads the form script only after a form
// of this DocType has been opened, so settings kept there are missing after a page refresh.

// Miller and PPC names are long ("SHREE SHYAMJI PADDY PROCESSING PVT LTD(M051007)"). The list normally
// cuts them with "...". Here those two columns are wider and wrap onto a second line, so the whole
// name is visible at a glance. Display only: nothing is saved.
// Season is the title field (first column), so the wide Miller style targets its own column.
const PPAS_LIST_STYLE_ID = "ivri-od-ppas-tp-list-style";

function add_ppas_list_style() {
	if (document.getElementById(PPAS_LIST_STYLE_ID)) return;
	const style = document.createElement("style");
	style.id = PPAS_LIST_STYLE_ID;
	style.textContent = `
		.ppas-tp-list .list-row-col[data-fieldname="miller"] { flex: 0 0 320px !important; width: 320px !important; min-width: 320px; }
		.ppas-tp-list .list-row-col[data-fieldname="ppc"] { flex: 0 0 230px !important; width: 230px !important; min-width: 230px; }
		.ppas-tp-list .list-row .list-row-col[data-fieldname="miller"],
		.ppas-tp-list .list-row .list-row-col[data-fieldname="miller"] .ellipsis,
		.ppas-tp-list .list-row .list-row-col[data-fieldname="miller"] a,
		.ppas-tp-list .list-row .list-row-col[data-fieldname="ppc"],
		.ppas-tp-list .list-row .list-row-col[data-fieldname="ppc"] .ellipsis,
		.ppas-tp-list .list-row .list-row-col[data-fieldname="ppc"] a {
			white-space: normal !important;
			overflow: visible !important;
			text-overflow: clip !important;
			overflow-wrap: anywhere;
			line-height: 1.35;
		}
		.ppas-tp-list .list-row { height: auto; min-height: var(--list-row-height, 40px); padding-top: 6px; padding-bottom: 6px; }
	`;
	document.head.appendChild(style);
}

frappe.listview_settings["PPAS Transit Pass"] = {
	// Hide the extra "ID" column (the pass unique key). Miller stays as the first column.
	// Display only: the ID is still the record name and is used in links and search.
	hide_name_column: true,

	onload(listview) {
		// Open with no filter: Frappe remembers the filters used last time, which hid data from staff.
		// A link with filters in its address (route options) is left alone.
		if (!Object.keys(frappe.route_options || {}).length && listview.filter_area) {
			listview.filter_area.clear();
		}
		add_ppas_list_style();
		listview.page.wrapper.addClass("ppas-tp-list");
	},
};
