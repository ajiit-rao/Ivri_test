// Copyright (c) 2026, Profezzo and contributors
// For license information, please see license.txt

// List view settings must live in this *_list.js file: Frappe loads the form script only after a form
// of this DocType has been opened, so settings kept there are missing after a page refresh.

// Mill Name holds "SHREE SHYAMJI PADDY PROCESSING PVT LTD(M051007)". The list shows the mill's Short Name
// from Mill Master (SSPPB), which is much shorter. Display only: nothing is saved.
const GRN_MILL_SHORT_NAMES = {};

function load_grn_mill_short_names() {
	return frappe.db.get_list("Mill Master", { fields: ["name", "short_name"], limit: 100 }).then((rows) => {
		(rows || []).forEach((row) => {
			if (row.short_name) GRN_MILL_SHORT_NAMES[row.name] = row.short_name;
		});
	});
}

// One GRN form for every weighment. GRN Type tells them apart; the buttons on top of the list filter on it.
const GRN_TYPE_BUTTONS = [
	{ label: "All", value: "" },
	{ label: "Government", value: "Government Paddy" },
	{ label: "Rice", value: "Rice Delivery to Depo" },
	{ label: "Private", value: "Private Deal" },
];
const GRN_TYPE_COLORS = { "Government Paddy": "blue", "Rice Delivery to Depo": "orange", "Private Deal": "purple" };

function add_grn_type_buttons(listview) {
	if (!listview.page || listview.grn_type_buttons) {
		return;
	}
	const $group = $('<div class="btn-group grn-type-buttons" role="group" style="margin-right:8px;"></div>');
	const mark = () => {
		const current = (listview.filter_area.get().find((f) => f[1] === "grn_type") || [])[3] || "";
		$group.find("button").each(function () {
			const active = $(this).attr("data-value") === current;
			$(this).toggleClass("btn-primary", active).toggleClass("btn-default", !active);
		});
	};
	GRN_TYPE_BUTTONS.forEach(({ label, value }) => {
		$(`<button type="button" class="btn btn-default btn-sm" data-value="${value}"></button>`)
			.text(__(label))
			.on("click", () => {
				const area = listview.filter_area;
				const done = value ? area.remove("grn_type").then(() => area.add([["GRN Note", "grn_type", "=", value]])) : area.remove("grn_type");
				Promise.resolve(done).then(mark);
			})
			.appendTo($group);
	});
	listview.page.page_actions.prepend($group);
	listview.grn_type_buttons = $group;
	mark();
}

frappe.listview_settings["GRN Note"] = {
	// GRN No is the first column; the ID column and the ID filter repeat it.
	hide_name_column: true,
	add_fields: ["grn_type"],
	get_indicator(doc) {
		const type = doc.grn_type || "Government Paddy";
		return [__(type), GRN_TYPE_COLORS[type] || "gray", `grn_type,=,${type}`];
	},
	onload(listview) {
		load_grn_mill_short_names().then(() => listview.refresh());
		add_grn_type_buttons(listview);
	},
	formatters: {
		mill_name(value) {
			const text = value || "";
			const code = (/\(([^)]+)\)\s*$/.exec(text) || [])[1] || text;
			const short = GRN_MILL_SHORT_NAMES[code.trim()] || text;
			return `<span class="ellipsis" title="${frappe.utils.escape_html(text)}">${frappe.utils.escape_html(short)}</span>`;
		},
	},
};
