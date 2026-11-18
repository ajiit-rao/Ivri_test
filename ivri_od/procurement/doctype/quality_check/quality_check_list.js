// Copyright (c) 2026, Profezzo and contributors
// For license information, please see license.txt

// List view settings must live in this *_list.js file: Frappe loads the form script only after a form
// of this DocType has been opened, so settings kept there are missing after a page refresh.

// Vehicle No is the title field, so it is always the first column.
// Only these columns show after it, in this order. Every other column is left out of the list.
const QC_LIST_COLUMN_ORDER = [
	"unloading_point_name",
	"paddy_received_in_pkt",
	"paddy_type",
	"type_of_pkt_summary",
	"paddy_quality",
	"moisture",
	"dust",
	"qc_datetime",
];

// Columns that are not "In List View" in the DocType, so the list adds them here.
const QC_EXTRA_LIST_COLUMNS = [
	"unloading_point_name",
	"paddy_received_in_pkt",
	"paddy_type",
	"type_of_pkt_summary",
	"moisture",
	"dust",
];

// Short list headings, so the columns fit. Display only: the form labels stay the same.
const QC_LIST_LABELS = {
	unloading_point_name: "Warehouse",
	qc_datetime: "Date",
	paddy_received_in_pkt: "Received Bags",
	paddy_type: "Paddy Type",
	type_of_pkt_summary: "Bag Type",
	paddy_quality: "Quality",
	moisture: "Moisture %",
	dust: "Dust Kg",
};

// Column widths in pixels, wide enough for the longest value (for example "Jute 456, Plastic 0").
// Staff can still drag a column edge to change a width.
const QC_LIST_WIDTHS = {
	vehicle_no: 150,
	unloading_point_name: 180,
	paddy_received_in_pkt: 130,
	paddy_type: 160,
	type_of_pkt_summary: 190,
	paddy_quality: 120,
	moisture: 120,
	dust: 100,
	qc_datetime: 120,
};

// Long values wrap onto a second line instead of being cut with "...", so nothing is hidden.
// Display only: nothing is saved.
const QC_LIST_STYLE_ID = "ivri-od-qc-list-style";

function add_qc_list_style() {
	if (document.getElementById(QC_LIST_STYLE_ID)) return;
	const style = document.createElement("style");
	style.id = QC_LIST_STYLE_ID;
	style.textContent = `
		.qc-list .list-row-col,
		.qc-list .list-row-col .ellipsis,
		.qc-list .list-row-col a,
		.qc-list .list-row-col span {
			white-space: normal !important;
			overflow: visible !important;
			text-overflow: clip !important;
			overflow-wrap: anywhere;
			line-height: 1.35;
		}
		.qc-list .list-row-head .list-row-col { font-weight: 600; }
		.qc-list .list-row { height: auto; min-height: var(--list-row-height, 40px); padding-top: 6px; padding-bottom: 6px; }
	`;
	document.head.appendChild(style);
}

function ensure_qc_list_columns(listview) {
	const present = new Set(
		(listview.columns || [])
			.filter((col) => col.type === "Field" && col.df)
			.map((col) => col.df.fieldname)
	);

	let changed = false;
	for (const fieldname of QC_EXTRA_LIST_COLUMNS) {
		if (present.has(fieldname)) {
			continue;
		}

		const df = frappe.meta.get_docfield("Quality Check", fieldname);
		if (!df) {
			continue;
		}

		listview.columns.push({ type: "Field", df: Object.assign({}, df, { hidden: 0 }) });
		changed = true;
	}

	return changed;
}

function apply_qc_list_labels(listview) {
	(listview.columns || []).forEach((col) => {
		if (!col.df) return;
		const fieldname = col.df.fieldname;
		const label = col.type === "Field" && QC_LIST_LABELS[fieldname];
		const width = QC_LIST_WIDTHS[fieldname];
		if (label || width) {
			// Copy the field so the short heading and width are used in the list only.
			col.df = Object.assign({}, col.df, label ? { label } : {}, width ? { width } : {});
		}
	});
}

function reorder_qc_list_columns(listview) {
	const columns = listview.columns || [];
	const fixed = columns.filter(
		(col) => col.type === "Subject" || col.type === "Tag" || col.type === "Status"
	);
	const by_fieldname = {};

	columns
		.filter((col) => col.type === "Field" && col.df)
		.forEach((col) => {
			by_fieldname[col.df.fieldname] = col;
		});

	const ordered = [...fixed];
	for (const fieldname of QC_LIST_COLUMN_ORDER) {
		if (by_fieldname[fieldname]) {
			ordered.push(by_fieldname[fieldname]);
			delete by_fieldname[fieldname];
		}
	}

	// Any other column (Farmer Name, Staff, Quality Test, ...) is not shown.
	listview.columns = ordered;
}

function setup_qc_list_columns(listview) {
	const added = ensure_qc_list_columns(listview);
	apply_qc_list_labels(listview);
	reorder_qc_list_columns(listview);
	return added;
}

frappe.listview_settings["Quality Check"] = {
	add_fields: [
		"unloading_point_name",
		"qc_datetime",
		"paddy_received_in_pkt",
		"paddy_type",
		"type_of_pkt_summary",
		"paddy_quality",
		"moisture",
		"dust",
	],

	formatters: {
		// Show the date only. Display only: the time is still saved and shown on the form.
		qc_datetime(value) {
			if (!value) {
				return "";
			}
			const date = frappe.utils.escape_html(
				frappe.datetime.str_to_user(String(value).split(/[ T]/)[0])
			);
			return `<span class="ellipsis" title="${date}">${date}</span>`;
		},
	},

	onload(listview) {
		// A saved column layout keeps only the columns named in it, and Frappe rebuilds the columns when
		// that layout loads. So re-apply our columns after every rebuild.
		const frappe_setup_columns = listview.setup_columns.bind(listview);
		listview.setup_columns = async function (...args) {
			await frappe_setup_columns(...args);
			setup_qc_list_columns(listview);
		};

		add_qc_list_style();
		listview.page.wrapper.addClass("qc-list");

		if (setup_qc_list_columns(listview)) {
			listview.refresh(true);
		}
	},
};
