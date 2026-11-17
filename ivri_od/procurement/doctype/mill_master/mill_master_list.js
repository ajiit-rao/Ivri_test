// Copyright (c) 2026, Profezzo and contributors
// For license information, please see license.txt

// List view settings must live in this *_list.js file: Frappe loads the form script only after a form
// of this DocType has been opened, so settings kept there are missing after a page refresh.
frappe.listview_settings["Mill Master"] = {
	// Hide the extra "ID" column (the miller code). Short Name stays as the first column.
	// Display only: the ID is still the record name and is used in links and search.
	hide_name_column: true,
};
