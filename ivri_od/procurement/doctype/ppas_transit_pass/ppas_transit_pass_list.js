// Copyright (c) 2026, Profezzo and contributors
// For license information, please see license.txt

// List view settings must live in this *_list.js file: Frappe loads the form script only after a form
// of this DocType has been opened, so settings kept there are missing after a page refresh.

// Miller and PPC names are long ("SHREE SHYAMJI PADDY PROCESSING PVT LTD(M051007)"). The list normally
// cuts them with "...". Here those two columns are wider and wrap onto a second line, so the whole
// name is visible at a glance. Display only: nothing is saved.
// Miller is the first column (the list changes it from Season), so the wide Miller style targets its own column.
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


// The list shows only these columns, in this order. Season is not shown: staff use it as a filter.
// Frappe always makes the title field (Season) the first column, so the first column is changed to
// Miller here. Display only: nothing is saved, and the form is unchanged.
const PPAS_LIST_COLUMN_ORDER = [
	"miller",
	"ppc",
	"vehicle_no",
	"transit_pass_no",
	"bags",
	"quantity",
	"transit_pass_date",
	"accepted_date",
	"delay_in_days",
];

// Short list headings. Display only: form labels stay the same.
const PPAS_LIST_LABELS = {
	transit_pass_no: "TP No",
	bags: "Bags",
	transit_pass_date: "TP Date",
};

// Widths in pixels, wide enough for the bold heading and the longest normal value, so headings do
// not overlap. Staff can still drag a column edge to change a width.
const PPAS_LIST_WIDTHS = {
	miller: 320,
	ppc: 230,
	vehicle_no: 140,
	transit_pass_no: 140,
	bags: 100,
	quantity: 110,
	transit_pass_date: 130,
	accepted_date: 150,
	delay_in_days: 170,
};

function ppas_list_column(fieldname, existing) {
	const df = (existing && existing.df) || frappe.meta.get_docfield("PPAS Transit Pass", fieldname);
	if (!df) {
		return null;
	}

	// Copy the field so the heading, width and "not hidden" apply only in the list.
	return Object.assign({}, df, {
		hidden: 0,
		label: PPAS_LIST_LABELS[fieldname] || df.label,
		width: PPAS_LIST_WIDTHS[fieldname] || df.width,
	});
}

function setup_ppas_transit_pass_list_columns(listview) {
	const columns = listview.columns || [];
	const signature = columns.map((col) => (col.df && col.df.fieldname) || col.type).join("|");

	const existing = {};
	columns
		.filter((col) => col.type === "Field" && col.df)
		.forEach((col) => {
			existing[col.df.fieldname] = col;
		});

	// The first column is the Subject (it holds the link that opens the record).
	const subject = columns.find((col) => col.type === "Subject");
	const tag = columns.find((col) => col.type === "Tag");
	const status = columns.find((col) => col.type === "Status");
	const [first, ...rest] = PPAS_LIST_COLUMN_ORDER;

	const ordered = [];
	const first_df = ppas_list_column(first, existing[first]);
	if (subject && first_df) {
		ordered.push(Object.assign({}, subject, { df: first_df }));
	} else if (subject) {
		ordered.push(subject);
	}
	if (tag) ordered.push(tag);
	if (status) ordered.push(status);

	for (const fieldname of rest) {
		const df = ppas_list_column(fieldname, existing[fieldname]);
		if (df) {
			ordered.push({ type: "Field", df });
		}
	}

	listview.columns = ordered;
	return signature !== ordered.map((col) => (col.df && col.df.fieldname) || col.type).join("|");
}

// The list filters, in this order. The text filters are drop-downs of the values that exist in the
// transit passes (for example Kharif(2025) for Season); the two date filters open a calendar.
// Frappe places the filters in the order of the form fields, so they are moved into this order.
// The filter fields are made a moment after the list opens, so wait for them.
const PPAS_DROPDOWN_FILTERS = ["season", "transit_pass_no", "miller", "ppc", "vehicle_no", "action"];
const PPAS_FILTER_ORDER = [...PPAS_DROPDOWN_FILTERS, "transit_pass_date", "accepted_date"];
// Short placeholder for the date filters. Display only: form labels stay the same.
const PPAS_FILTER_PLACEHOLDERS = { transit_pass_date: "TP Date" };

const PPAS_DATE_FILTERS = ["transit_pass_date", "accepted_date"];

// Frappe's date filter does not refresh the list when its date is removed (it sees "no value" as "no
// change"), so the list kept showing the old date's records. Refresh the list when the date is cleared.
function refresh_list_when_date_filter_cleared(listview, field) {
	if (!field.$input || field.__ppas_clear_bound) {
		return;
	}
	field.__ppas_clear_bound = true;
	field.$input.on("input change", () => {
		if (!(field.$input.val() || "").trim()) {
			listview.filter_area.debounced_refresh_list_view();
		}
	});
}

function setup_ppas_filters(listview) {
	frappe
		.xcall("ivri_od.procurement.doctype.ppas_transit_pass.ppas_transit_pass.get_filter_values")
		.then((values) => {
			let tries = 0;
			const timer = setInterval(() => {
				tries += 1;
				const fields = listview.page.fields_dict || {};
				const ready = PPAS_FILTER_ORDER.filter((name) => fields[name]);
				if (ready.length === PPAS_FILTER_ORDER.length || tries > 40) {
					clearInterval(timer);
					ready.forEach((name) => {
						const field = fields[name];
						if (PPAS_DROPDOWN_FILTERS.includes(name) && field.set_data) {
							field.set_data(values[name] || []);
						}
						const placeholder = PPAS_FILTER_PLACEHOLDERS[name];
						if (placeholder && field.$input) {
							field.$input.attr("placeholder", placeholder);
						}
						if (PPAS_DATE_FILTERS.includes(name)) {
							refresh_list_when_date_filter_cleared(listview, field);
						}
					});
					const $wrapper = $(fields[ready[0]]?.wrapper).parent();
					ready.forEach((name) => $wrapper.append(fields[name].wrapper));
				}
			}, 250);
		});
}

frappe.listview_settings["PPAS Transit Pass"] = {
	// Hide the extra "ID" column (the pass unique key). Miller stays as the first column.
	// Display only: the ID is still the record name and is used in links and search.
	hide_name_column: true,
	// No ID filter: Season, TP No, Miller, PPC, Vehicle No, Action, TP Date and Accepted Date are the filters staff use.
	hide_name_filter: true,

	add_fields: [
		"miller",
		"ppc",
		"vehicle_no",
		"transit_pass_no",
		"bags",
		"quantity",
		"transit_pass_date",
		"accepted_date",
		"delay_in_days",
	],

	onload(listview) {
		// A saved column layout (List View Settings) keeps only the columns named in it, and Frappe
		// rebuilds the columns when that layout loads. So re-apply our columns after every rebuild.
		const frappe_setup_columns = listview.setup_columns.bind(listview);
		listview.setup_columns = async function (...args) {
			await frappe_setup_columns(...args);
			setup_ppas_transit_pass_list_columns(listview);
		};

		if (setup_ppas_transit_pass_list_columns(listview)) {
			listview.refresh(true);
		}
		setup_ppas_filters(listview);

		// Open with no filter: Frappe remembers the filters used last time, which hid data from staff.
		// A link with filters in its address (route options) is left alone.
		if (!Object.keys(frappe.route_options || {}).length && listview.filter_area) {
			listview.filter_area.clear();
		}
		add_ppas_list_style();
		listview.page.wrapper.addClass("ppas-tp-list");

		if (frappe.user.has_role("System Manager")) {
			listview.page.add_menu_item(__("Delete All Transit Passes"), () => {
				frappe.confirm(
					__(
						"Permanently delete ALL PPAS Transit Pass records? This cannot be undone."
					),
					() => {
						frappe.call({
							method:
								"ivri_od.procurement.doctype.ppas_transit_pass.ppas_transit_pass.delete_all_transit_passes",
							freeze: true,
							freeze_message: __("Deleting..."),
							callback(r) {
								frappe.show_alert({
									message: r.message || __("Deleted"),
									indicator: "green",
								});
								listview.refresh();
							},
						});
					}
				);
			});
		}
	},
};
