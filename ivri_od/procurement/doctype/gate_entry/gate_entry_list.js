// Copyright (c) 2026, Profezzo and contributors
// For license information, please see license.txt

// List view settings must live in this *_list.js file: Frappe loads the form script only after a form
// of this DocType has been opened, so settings kept there are missing after a page refresh.
// Purpose column: Gate In keeps its purpose in "Purpose", Gate Out in "Out Purpose". The list shows
// whichever is filled, and adds the details when it is "Others". Display only: nothing is saved.
const GATE_ENTRY_PURPOSE_WIDTH = 190;

function ensure_gate_entry_purpose_column(listview) {
	const present = (listview.columns || []).some(
		(col) => col.type === "Field" && col.df && col.df.fieldname === "in_purpose"
	);
	if (present) {
		return false;
	}

	const df = frappe.meta.get_docfield("Gate Entry", "in_purpose");
	if (!df) {
		return false;
	}

	// Copy the field so the width applies in the list only. Frappe reads the width of a column from it.
	listview.columns.push({
		type: "Field",
		df: Object.assign({}, df, { width: GATE_ENTRY_PURPOSE_WIDTH }),
	});
	return true;
}

// Purpose comes right after Vehicle No (the first column); the other columns keep their order.
function move_gate_entry_purpose_column(listview) {
	const columns = listview.columns || [];
	const index = columns.findIndex(
		(col) => col.type === "Field" && col.df && col.df.fieldname === "in_purpose"
	);
	if (index < 0) {
		return;
	}

	const [purpose] = columns.splice(index, 1);
	const subject = columns.findIndex((col) => col.type === "Subject");
	columns.splice(subject + 1, 0, purpose);
	// Keep the Tag column (if any) right after Vehicle No, where Frappe puts it.
	const tag = columns.findIndex((col) => col.type === "Tag");
	if (tag > subject + 1) {
		columns.splice(subject + 1, 0, columns.splice(tag, 1)[0]);
	}
}

function setup_gate_entry_purpose_column(listview) {
	const added = ensure_gate_entry_purpose_column(listview);
	move_gate_entry_purpose_column(listview);
	return added;
}

frappe.listview_settings["Gate Entry"] = {
	add_fields: ["in_purpose", "out_purpose", "purpose", "out_purpose_detail"],

	formatters: {
		in_purpose(value, df, doc) {
			const purpose = value || doc.out_purpose || "";
			const detail =
				purpose === "Others" ? doc.purpose || doc.out_purpose_detail || "" : "";
			const text = frappe.utils.escape_html(detail ? `${purpose}: ${detail}` : purpose);
			return `<span class="ellipsis" title="${text}">${text}</span>`;
		},
	},

	// Vehicle No is the title field, so it shows as the first column. Hide the extra "ID" column.
	// Display only: the ID is still the record name and is used in links and search.
	hide_name_column: true,

	onload(listview) {
		// Frappe rebuilds the columns when a saved column layout loads, so re-apply after every rebuild.
		const frappe_setup_columns = listview.setup_columns.bind(listview);
		listview.setup_columns = async function (...args) {
			await frappe_setup_columns(...args);
			setup_gate_entry_purpose_column(listview);
		};
		if (setup_gate_entry_purpose_column(listview)) {
			listview.refresh(true);
		}

		listview.page.add_inner_button(__("Inside Mill"), () => {
			listview.filter_area.clear();
			listview.filter_area.add([
				["Gate Entry", "in_out", "=", "In"],
				["Gate Entry", "inside_mill", "=", 1],
			]);
		});
	},
};
