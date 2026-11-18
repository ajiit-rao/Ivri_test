// Copyright (c) 2026, Profezzo and contributors
// For license information, please see license.txt

// List view settings must live in this *_list.js file: Frappe loads the form script only after a form
// of this DocType has been opened, so settings kept there are missing after a page refresh.
frappe.listview_settings["Target Allocation"] = {
	// Season is the title field, so it shows as the first column. Hide the extra "ID" column
	// (a random code that means nothing to staff).
	// Display only: the ID is still the record name and is used in links and search.
	hide_name_column: true,
};
