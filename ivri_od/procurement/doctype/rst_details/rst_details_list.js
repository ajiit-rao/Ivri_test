// Copyright (c) 2026, Profezzo and contributors
// For license information, please see license.txt

// List view settings must live in this *_list.js file: Frappe loads the form script only after a form
// of this DocType has been opened, so settings kept there are missing after a page refresh.
frappe.listview_settings["RST Details"] = {
	// RST No is the title field (first column) and is also the ID, so the extra "ID" column repeats it.
	// Display only: the ID is still the record name and is used in links and search.
	hide_name_column: true,
	// The "ID" filter repeats RST No, so it is not shown.
	hide_name_filter: true,

	onload(listview) {
		// A saved column layout can list "ID" as a column. Frappe rebuilds the columns when that layout
		// loads, so take the ID column out after every rebuild.
		const frappe_setup_columns = listview.setup_columns.bind(listview);
		listview.setup_columns = async function (...args) {
			await frappe_setup_columns(...args);
			listview.columns = (listview.columns || []).filter(
				(col) => !(col.type === "Field" && col.df && col.df.fieldname === "name")
			);
		};
		listview.columns = (listview.columns || []).filter(
			(col) => !(col.type === "Field" && col.df && col.df.fieldname === "name")
		);

		// Open with no filter: Frappe remembers the filters used last time, which hid data from staff.
		// A link with filters in its address (route options) is left alone.
		if (!Object.keys(frappe.route_options || {}).length && listview.filter_area) {
			listview.filter_area.clear();
		}

		make_filters_dropdown(listview);
	},
};

// Every filter above the list is a dropdown that lists the values already saved, so staff pick
// instead of typing. Values are read once when the list opens.
const DROPDOWN_FILTERS = ["rst_no", "vehicle_no", "tp_no", "party_name", "season_code"];

async function make_filters_dropdown(listview) {
	const wrapper = listview.filter_area && listview.filter_area.standard_filters_wrapper;
	if (!wrapper) return;

	const names = DROPDOWN_FILTERS.filter((n) => listview.page.fields_dict[n]);
	// Read all values first, so the boxes are rebuilt together and keep this order.
	const all_values = await Promise.all(
		names.map((fieldname) =>
			frappe.db
				.get_list("RST Details", {
					fields: [fieldname],
					group_by: fieldname,
					order_by: `${fieldname} asc`,
					limit: 0,
				})
				.then((rows) => rows.map((r) => r[fieldname]).filter(Boolean))
		)
	);

	names.forEach((fieldname, i) => {
		const old_field = listview.page.fields_dict[fieldname];
		const current_value = old_field.get_value();
		const label = old_field.df.label;
		$(old_field.wrapper).remove();
		delete listview.page.fields_dict[fieldname];

		const field = listview.page.add_field(
			{
				fieldtype: "Autocomplete",
				fieldname: fieldname,
				label: label,
				options: all_values[i],
				condition: "=",
				is_filter: 1,
				onchange: () => listview.filter_area.debounced_refresh_list_view(),
			},
			wrapper
		);
		if (current_value) field.set_value(current_value);
	});
}
