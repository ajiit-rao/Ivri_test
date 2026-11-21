// Copyright (c) 2026, Profezzo and contributors

// Excess Received Qty: press Edit on top, then click the cell of a Transit Pass. The quantity is
// saved (Chhatni Excess) and the Chhatni (QT) and Received Chhatni % of that pass are worked out again.
frappe.provide("ivri_od.mandi_book");
ivri_od.mandi_book.edit_excess = function (pass_unique_key) {
	const report = frappe.query_report;
	const row = (report.data || []).find((d) => d.pass_unique_key === pass_unique_key && d.grn_lines) || {};
	const dialog = new frappe.ui.Dialog({
		title: __("Excess Received Qty, TP {0}", [row.transit_pass_no || ""]),
		fields: [
			{
				fieldname: "value",
				label: __("Excess Received Qty (QT)"),
				fieldtype: "Float",
				precision: 3,
				default: row.excess_received_qty || "",
				description: __(
					"Quantity received above the TP Qty that is paddy, not Chhatni. It is taken out of Chhatni (QT) and Received Chhatni %. Empty or 0 removes it."
				),
			},
		],
		primary_action_label: __("Save"),
		primary_action: ({ value }) => {
			frappe
				.xcall("ivri_od.procurement.report.mandi_book.mandi_book.set_excess_received_qty", {
					pass_unique_key,
					value: value || 0,
				})
				.then(() => {
					dialog.hide();
					frappe.show_alert({ message: __("Saved"), indicator: "green" });
					report.refresh();
				});
		},
	});
	dialog.show();
};

// Bags of an other TP (Edit, click its Jute / Plastic Bags): the bags of each of its trucks. They are saved on
// that TP's weighment (Bag Type) and taken off the truck's own TP, which keeps the rest of the truck's bags.
ivri_od.mandi_book.edit_bags = function (pass_unique_key) {
	const report = frappe.query_report;
	const row = (report.data || []).find((d) => d.pass_unique_key === pass_unique_key && d.grn_lines) || {};
	const lines = (row.grn_lines || []).filter((l) => l.is_other_tp && l.weigh_bridge_measurement);
	if (!lines.length) {
		frappe.msgprint(__("Bags can be given only to an other TP of a truck. The truck's own TP keeps the rest of the truck's bags."));
		return;
	}
	const dialog = new frappe.ui.Dialog({
		title: __("Bags of TP {0}", [row.transit_pass_no || ""]),
		size: "large",
		fields: [
			{
				fieldtype: "HTML",
				fieldname: "intro",
				options: `<p class="text-muted">${__("Give the Jute and Plastic bags this TP carried in each truck. They are taken off the truck's own TP, which keeps the rest of the truck's bags.")}</p>`,
			},
			{
				fieldname: "rows",
				fieldtype: "Table",
				label: __("Trucks"),
				cannot_add_rows: true,
				cannot_delete_rows: true,
				in_place_edit: true,
				data: lines.map((l) => ({
					weighment: l.weigh_bridge_measurement,
					rst_no: l.rst_no,
					grn_no: l.grn_no,
					jute_bags: cint(l.jute_pkt),
					plastic_bags: cint(l.plastic_pkt),
				})),
				fields: [
					{ fieldname: "rst_no", fieldtype: "Data", label: __("RST No"), in_list_view: 1, read_only: 1, columns: 2 },
					{ fieldname: "grn_no", fieldtype: "Data", label: __("GRN No"), in_list_view: 1, read_only: 1, columns: 2 },
					{ fieldname: "jute_bags", fieldtype: "Int", label: __("Jute Bags"), in_list_view: 1, columns: 2 },
					{ fieldname: "plastic_bags", fieldtype: "Int", label: __("Plastic Bags"), in_list_view: 1, columns: 2 },
					{ fieldname: "weighment", fieldtype: "Link", options: "Weigh Bridge Measurement", label: __("Weighment"), in_list_view: 1, read_only: 1, columns: 2 },
				],
			},
		],
		primary_action_label: __("Save"),
		primary_action: async (values) => {
			const rows = values.rows || [];
			if (rows.some((r) => cint(r.jute_bags) < 0 || cint(r.plastic_bags) < 0)) {
				frappe.msgprint(__("Bags cannot be less than 0."));
				return;
			}
			const before = {};
			lines.forEach((l) => (before[l.weigh_bridge_measurement] = [cint(l.jute_pkt), cint(l.plastic_pkt)]));
			for (const r of rows) {
				const old = before[r.weighment] || [];
				if (old[0] === cint(r.jute_bags) && old[1] === cint(r.plastic_bags)) continue;
				await frappe.xcall("ivri_od.procurement.other_tp.save_other_tp_bags", {
					wbm_name: r.weighment,
					jute_bags: cint(r.jute_bags),
					plastic_bags: cint(r.plastic_bags),
				});
			}
			dialog.hide();
			frappe.show_alert({ message: __("Bags saved"), indicator: "green" });
			report.refresh();
		},
	});
	dialog.show();
};

// RST No: one weighment that holds the goods of several Transit Passes. Staff learn this later, so in Edit
// mode they click the RST No, choose each TP No (from PPAS Transit Pass, same PPC and season) and give it
// its Qty. The Qty of all rows must equal the RST Net Qty. The GRN Note itself is not changed.
ivri_od.mandi_book.attach_tp = function (grn_name) {
	const report = frappe.query_report;
	const api = "ivri_od.procurement.report.mandi_book.mandi_book.";
	frappe.xcall(api + "get_tp_split", { grn_name }).then((info) => {
		const dialog = new frappe.ui.Dialog({
			title: __("RST {0}: attach TP No", [info.rst_no || ""]),
			size: "large",
			fields: [
				{
					fieldtype: "HTML",
					fieldname: "intro",
					options: `<p class="text-muted">${__("RST Net Qty: {0} QT. The Qty of the TP Nos below must add up to it.", [format_number(info.net_qty, null, 3)])}</p>`,
				},
				{
					fieldname: "rows",
					fieldtype: "Table",
					label: __("TP No and Qty"),
					cannot_add_rows: false,
					in_place_edit: true,
					data: info.rows,
					fields: [
						{
							fieldname: "transit_pass_no",
							fieldtype: "Select",
							label: __("TP No"),
							options: ["", ...info.choices].join("\n"),
							in_list_view: 1,
							reqd: 1,
							columns: 5,
						},
						{
							fieldname: "qty",
							fieldtype: "Float",
							label: __("Qty (QT)"),
							precision: 3,
							in_list_view: 1,
							reqd: 1,
							columns: 4,
						},
					],
				},
			],
			primary_action_label: __("Save"),
			primary_action: ({ rows }) => {
				const clean = (rows || []).filter((r) => r.transit_pass_no || flt(r.qty));
				const total = flt(clean.reduce((sum, r) => sum + flt(r.qty), 0), 3);
				if (Math.abs(total - flt(info.net_qty, 3)) > 0.001) {
					frappe.msgprint(
						__("The Qty adds up to {0} QT but the RST Net Qty is {1} QT. They must be equal.", [total, flt(info.net_qty, 3)])
					);
					return;
				}
				frappe.xcall(api + "save_tp_split", { grn_name, rows: JSON.stringify(clean) }).then(() => {
					dialog.hide();
					frappe.show_alert({ message: __("Saved"), indicator: "green" });
					report.refresh();
				});
			},
		});
		if (info.has_split) {
			dialog.set_secondary_action_label(__("Back to one TP No"));
			dialog.set_secondary_action(() => {
				frappe.xcall(api + "clear_tp_split", { grn_name }).then(() => {
					dialog.hide();
					frappe.show_alert({ message: __("Saved"), indicator: "green" });
					report.refresh();
				});
			});
		}
		dialog.show();
	});
};

// RST No: this truck also carried paddy of other Transit Passes. In Edit mode staff click the RST No and
// list the other TPs (TP No, PPC Name, Mill No, Qty). On save each other TP gets its own weighment and GRN
// (same RST, Quality Check and vehicle) with its Qty, and this TP keeps the rest of the RST Net Weight.
ivri_od.mandi_book.other_tps = function (wbm_name) {
	const report = frappe.query_report;
	const api = "ivri_od.procurement.other_tp.";
	frappe.xcall(api + "get_other_tps", { wbm_name }).then((rst) => {
		// All TPs of the RST in one table: the RST's own TP first (read only), then the other TPs.
		(rst.all_tps || []).forEach((r) => {
			if (r.ppc_name && r.ppc_label) frappe.utils.add_link_title("PPC Master", r.ppc_name, r.ppc_label);
			if (r.mill_no && r.mill_label) frappe.utils.add_link_title("Mill Master", r.mill_no, r.mill_label);
		});
		// Row 1 (this RST's own TP) keeps its values: its Deduction comes from RST Details / Quality Check.
		const own_row = (rst.all_tps || []).find((r) => r.is_own) || {};
		// Other TP rows: Net Weight = Gross Weight - Gunny Weight - Deduction, worked out while typing.
		function net_of_row() {
			const row = this.grid_row && this.grid_row.doc;
			if (!row) return;
			if (row.is_own) {
				row.qty = own_row.qty;
				row.gunny_weight = own_row.gunny_weight;
				row.deduction = own_row.deduction;
				row.jute_bags = own_row.jute_bags;
				row.plastic_bags = own_row.plastic_bags;
				frappe.show_alert({ message: __("Row 1 is this RST's own TP. Its values come from the weighment."), indicator: "orange" });
			} else {
				row.net_weight = flt(flt(row.qty) - flt(row.gunny_weight) - flt(row.deduction), 3);
			}
			this.grid_row.refresh();
		}
		const dialog = new frappe.ui.Dialog({
			title: __("RST {0}: other TPs in this truck", [rst.rst_no || ""]),
			size: "extra-large",
			fields: [
				{
					fieldtype: "HTML",
					fieldname: "intro",
					options: `<p class="text-muted">${__("Gross Weight {3} QT, RST Net Weight {1} QT. Row 1 is this RST's own TP {0}: its Gross Weight is the truck's Gross Weight less the other TPs, worked out on save. Add the other TPs below it with their Gross Weight, Gunny Weight and Deduction; Net Weight = Gross Weight - Gunny Weight - Deduction. Row 1 keeps the rest of the truck's gunny and deduction, so all Net Weights add up to the RST Net Weight. On save each gets its own weighment and GRN (same RST, Quality Check and vehicle). Season left blank: {2}.", [frappe.utils.escape_html(rst.transit_pass_no || ""), format_number(rst.net_weight, null, 3), frappe.utils.escape_html(rst.season || "-"), format_number(rst.gross_weight, null, 3)])}</p>`,
				},
				{
					fieldname: "rows",
					fieldtype: "Table",
					label: __("Other TPs in this RST"),
					cannot_add_rows: false,
					in_place_edit: true,
					data: (rst.all_tps || rst.rows || []).map((r) => ({ ...r })),
					fields: [
						{ fieldname: "season", fieldtype: "Link", options: "Season Master", label: __("Season"), in_list_view: 1, columns: 1, default: rst.season || "" },
						{ fieldname: "transit_pass_no", fieldtype: "Data", label: __("TP No"), in_list_view: 1, reqd: 1, columns: 1 },
						{ fieldname: "ppc_name", fieldtype: "Link", options: "PPC Master", label: __("PPC Name"), in_list_view: 1, columns: 1 },
						{ fieldname: "mill_no", fieldtype: "Link", options: "Mill Master", label: __("Mill Name"), in_list_view: 1, columns: 1 },
						{ fieldname: "qty", fieldtype: "Float", label: __("Gross Weight (QT)"), precision: 3, in_list_view: 1, reqd: 1, columns: 1, onchange: net_of_row },
						{ fieldname: "gunny_weight", fieldtype: "Float", label: __("Gunny Weight (QT)"), precision: 3, in_list_view: 1, columns: 1, onchange: net_of_row },
						{ fieldname: "deduction", fieldtype: "Float", label: __("Deduction (QT)"), precision: 3, in_list_view: 1, columns: 1, onchange: net_of_row },
						{ fieldname: "net_weight", fieldtype: "Float", label: __("Net Weight"), precision: 3, in_list_view: 1, read_only: 1, columns: 1 },
						{ fieldname: "jute_bags", fieldtype: "Int", label: __("Jute Bags"), in_list_view: 1, columns: 1, onchange: net_of_row },
						{ fieldname: "plastic_bags", fieldtype: "Int", label: __("Plastic Bags"), in_list_view: 1, columns: 1, onchange: net_of_row },
						{ fieldname: "weighment", fieldtype: "Link", options: "Weigh Bridge Measurement", label: __("Weighment"), read_only: 1 },
						{ fieldname: "is_own", fieldtype: "Check", label: __("This RST's own TP"), read_only: 1, hidden: 1 },
					],
				},
			],
			primary_action_label: __("Save"),
			primary_action: (values) => {
				// Row of the RST's own TP is shown only: its Qty follows from the other TPs.
				const rows = (values.rows || []).filter((r) => !r.is_own && (r.transit_pass_no || flt(r.qty)));
				const total = flt(rows.reduce((sum, r) => sum + flt(r.qty), 0), 3);
				const bad = rows.find(
					(r) => flt(r.deduction) < 0 || flt(r.gunny_weight) < 0 || (flt(r.qty) > 0 && flt(r.gunny_weight) + flt(r.deduction) >= flt(r.qty))
				);
				if (bad) {
					frappe.msgprint(__("TP No {0}: Gunny Weight and Deduction must be 0 or more, and together less than its Gross Weight.", [frappe.utils.escape_html(bad.transit_pass_no || "")]));
					return;
				}
				if (rows.length && total >= flt(rst.net_weight, 3)) {
					frappe.msgprint(__("The Qty of the other TPs ({0} QT) must be less than the RST Net Weight ({1} QT).", [total, flt(rst.net_weight, 3)]));
					return;
				}
				// A split RST row opens its truck's weighment: save there.
				frappe.xcall(api + "save_other_tps", { wbm_name: rst.wbm_name || wbm_name, rows: JSON.stringify(rows) }).then((r) => {
					dialog.hide();
					const net = r.grn_net_weight == null ? "" : " " + __("GRN Net Weight of TP {0}: {1} QT.", [rst.transit_pass_no || "", format_number(r.grn_net_weight, null, 3)]);
					frappe.show_alert({ message: __("Saved.") + net, indicator: "green" });
					report.refresh();
				});
			},
		});
		// Wide box so every column of the table can be seen.
		dialog.$wrapper.find(".modal-dialog").css({ "max-width": "95vw", width: "95vw" });
		dialog.show();
	});
};

frappe.query_reports["Mandi Book"] = {
	collapsible_filters: true,
	onload(report) {
		ivri_od.report_edit.add_button(report, ["Excess Received Qty", "RST No (other TPs in this truck)", "Jute / Plastic Bags of an other TP"]);
		// No season is filled in: staff choose the season they want to see from the drop-down.
	},
	filters: [
		{
			fieldname: "season",
			label: __("Season"),
			fieldtype: "Link",
			options: "Season Master",
		},
		{
			fieldname: "district",
			label: __("District"),
			fieldtype: "Link",
			options: "District Master",
		},
		{
			fieldname: "mill_name",
			label: __("Mill Name (Code)"),
			fieldtype: "Link",
			options: "Mill Master",
		},
		{
			fieldname: "ppc_name",
			label: __("PPC Name"),
			fieldtype: "Link",
			options: "PPC Master",
		},
		{
			fieldname: "transit_pass_no",
			label: __("TP No"),
			fieldtype: "Data",
		},
	],
	formatter(value, row, column, data, default_formatter) {
		const fieldname = (column && (column.fieldname || column.id)) || "";
		if (data && data.pass_unique_key) {
			window.__mandi_book_rows = window.__mandi_book_rows || {};
			window.__mandi_book_rows[data.pass_unique_key] = data;
		}

		if (value == null || value === "") {
			return "";
		}

		if (fieldname === "grn_count" || fieldname === "rst_count" || fieldname === "entry_count") {
			return `<span class="text-muted font-weight-bold">${frappe.utils.escape_html(String(value))}</span>`;
		}

		if (fieldname === "detail_type") {
			if (value === "GRN") {
				return `<span class="indicator-pill green">${__("GRN")}</span>`;
			}
			if (value === "Entry") {
				return `<span class="indicator-pill blue">${__("Entry")}</span>`;
			}
			if (value === "GRN & Entry") {
				return `<span class="indicator-pill green">${__("GRN")}</span> <span class="indicator-pill blue">${__("Entry")}</span>`;
			}
			return `<span class="indicator-pill gray">${frappe.utils.escape_html(value)}</span>`;
		}

		if (fieldname === "grn_no") {
			const docname = (data && data.grn_name) || value;
			const link = frappe.utils.get_form_link("GRN Note", docname);
			return `<a href="${link}">${frappe.utils.escape_html(value)}</a>`;
		}

		if (fieldname === "rst_no") {
			let html = frappe.utils.escape_html(value);
			if (data && data.weigh_bridge_measurement) {
				const link = frappe.utils.get_form_link("Weigh Bridge Measurement", data.weigh_bridge_measurement);
				html = `<a href="${link}">${html}</a>`;
			}
			if (data && data.split_qty != null) {
				html += ` <span class="text-muted" title="${__("This RST is shared by several TP Nos. Qty for this TP No: {0}", [data.split_qty])}">⇄ ${data.split_qty}</span>`;
			}
			if (data && flt(data.other_tp_qty) > 0) {
				// This RST also carried other TPs: show this TP's own Qty (Gross - Other TPs).
				const own = flt(data.rst_tp_qty) || flt(data.net_weight);
				html += ` <span class="text-muted" title="${__("This RST also carried {0} QT of other TPs. Qty of this TP: {1} QT (Gross - Other TPs).", [data.other_tp_qty, own])}">⇄ ${own}</span>`;
			}
			if (data && data.grn_name && data.split_qty != null) {
				// An RST split earlier over several TP Nos keeps its old box ("Back to one TP No").
				return ivri_od.report_edit.cell(
					html,
					`ivri_od.mandi_book.attach_tp(decodeURIComponent('${encodeURIComponent(String(data.grn_name)).replace(/'/g, "%27")}'))`,
					true
				);
			}
			if (data && data.grn_name && data.weigh_bridge_measurement) {
				// Edit mode: click the RST No to list the other TPs carried in this truck.
				return ivri_od.report_edit.cell(
					html,
					`ivri_od.mandi_book.other_tps(decodeURIComponent('${encodeURIComponent(String(data.weigh_bridge_measurement)).replace(/'/g, "%27")}'))`,
					flt(data.other_tp_qty) > 0
				);
			}
			return html;
		}

		if (fieldname === "entry") {
			const link = frappe.utils.get_form_link("Entry", value);
			return `<a href="${link}">${frappe.utils.escape_html(value)}</a>`;
		}

		if (fieldname === "chhatni_status") {
			return mandi_book_status_pill(value);
		}

		if (fieldname === "tp_status") {
			const indicator = value === __("TP Completed") ? "green" : (value === __("Pending") ? "gray" : "orange");
			return `<span class="indicator-pill ${indicator}">${frappe.utils.escape_html(value)}</span>`;
		}

		if (
			(fieldname === "jute_pkt" || fieldname === "plastic_pkt") &&
			data && data.pass_unique_key && (data.grn_lines || []).some((l) => l.is_other_tp)
		) {
			return ivri_od.report_edit.cell(
				default_formatter(value, row, column, data),
				`ivri_od.mandi_book.edit_bags(decodeURIComponent('${encodeURIComponent(String(data.pass_unique_key)).replace(/'/g, "%27")}'))`,
				cint(data.jute_pkt) + cint(data.plastic_pkt) > 0
			);
		}

		if (fieldname === "excess_received_qty" && data && data.pass_unique_key && data.grn_lines) {
			return ivri_od.report_edit.cell(
				default_formatter(value, row, column, data),
				`ivri_od.mandi_book.edit_excess(decodeURIComponent('${encodeURIComponent(String(data.pass_unique_key)).replace(/'/g, "%27")}'))`,
				flt(value) > 0
			);
		}

		return default_formatter(value, row, column, data);
	},
	after_datatable_render(datatable) {
		apply_mandi_book_grouping(datatable);
		render_mandi_book_super_header(datatable);
	},
	show_popup(kind, data) {
		mandi_book_dialog(kind, data || {});
	},
};

function apply_mandi_book_grouping(datatable) {
	if (!datatable || !datatable.datamanager) {
		return;
	}

	const rows = datatable.datamanager.data || [];
	const totalRows = rows.length;
	const viewOrder =
		datatable.datamanager.rowViewOrder && datatable.datamanager.rowViewOrder.length === totalRows
			? datatable.datamanager.rowViewOrder
			: Array.from({ length: totalRows }, (_, i) => i);

	let current_tp = 0;
	const tp_sr_map = {};
	const group_end_indices = [];

	for (let v = 0; v < viewOrder.length; v++) {
		const rowIndex = viewOrder[v];
		const d = datatable.datamanager.getData(rowIndex);
		const isFirstRow = Boolean(d && (d.pass_unique_key || d.transit_pass_no));
		if (isFirstRow) {
			current_tp += 1;
			tp_sr_map[rowIndex] = String(current_tp);
		} else {
			tp_sr_map[rowIndex] = "";
		}

		const nextRowIndex = viewOrder[v + 1];
		const next_d = nextRowIndex != null ? datatable.datamanager.getData(nextRowIndex) : null;
		const isLastRowOfGroup =
			v === viewOrder.length - 1 || Boolean(next_d && (next_d.pass_unique_key || next_d.transit_pass_no));
		if (isLastRowOfGroup) {
			group_end_indices.push(rowIndex);
		}
	}

	const srNoColIndex = datatable.datamanager.getColumnIndexById("_rowIndex");
	const srNoCol = datatable.datamanager.getColumnById("_rowIndex");

	if (srNoCol) {
		srNoCol.format = (value, row, column, data) => {
			const rowIndex =
				row && row.meta && row.meta.rowIndex != null
					? row.meta.rowIndex
					: row && row[0] && row[0].rowIndex != null
					? row[0].rowIndex
					: data && data.rowIndex != null
					? data.rowIndex
					: null;
			if (rowIndex != null && tp_sr_map[rowIndex] !== undefined) {
				return tp_sr_map[rowIndex];
			}
			if (data && (data.pass_unique_key || data.transit_pass_no)) {
				return value || "";
			}
			return "";
		};
	}

	if (srNoColIndex >= 0 && datatable.datamanager.rows) {
		datatable.datamanager.rows.forEach((row, i) => {
			const cell = row[srNoColIndex];
			if (cell) {
				const val = tp_sr_map[i] != null ? tp_sr_map[i] : "";
				cell.content = val;
				cell.html = val;
			}
		});
	}

	const columns = (datatable && datatable.datamanager && typeof datatable.datamanager.getColumns === "function")
		? datatable.datamanager.getColumns()
		: [];
	const summaryColIndices = [];
	const entryColIndices = [];
	const grnColIndices = [];
	let rowIndexColIndex = -1;
	let grnColIndex = -1;
	let entryColIndex = -1;
	let lastGrnColIndex = -1;

	const summaryFieldnames = new Set([
		"season",
		"ppc_name_slip_no",
		"ppc_name",
		"rst_no",
		"mill_name",
		"transit_pass_no",
		"pass_unique_key",
		"tp_quantity",
		"total_gross_weight",
		"total_other_tp_qty",
		"summary_gunny_type",
		"total_gunny_weight",
		"total_deduction_received",
		"chhatni_received_qty",
		"total_received",
		"pending_qty",
		"excess_received_qty",
		"tp_status",
		"jute_pkt",
		"plastic_pkt",
		"total_bags",
		"chhatni_assigned",
		"actual_chhatni_pct",
		"chhatni_status"
	]);

	const entryFieldnames = new Set([
		"entry",
		"agent_name",
		"entry_quantity",
		"entry_price_per_quintal",
		"total_amount"
	]);

	const grnFieldnames = new Set([
		"grn_no",
		"rst_no",
		"vehicle_no",
		"load_weight",
		"tare_weight",
		"gross_weight",
		"other_tp_qty",
		"gunny_type",
		"gunny_weight",
		"deduction",
		"net_weight"
	]);

	columns.forEach((c) => {
		const fn = c.id || c.fieldname || "";
		const idx = c.colIndex != null ? c.colIndex : -1;
		if (idx < 0) return;

		if (fn === "_rowIndex") {
			rowIndexColIndex = idx;
		} else if (summaryFieldnames.has(fn)) {
			summaryColIndices.push(idx);
		} else if (entryFieldnames.has(fn)) {
			entryColIndices.push(idx);
			if (fn === "entry") entryColIndex = idx;
		} else if (grnFieldnames.has(fn)) {
			grnColIndices.push(idx);
			if (fn === "grn_no") grnColIndex = idx;
			if (fn === "net_weight") lastGrnColIndex = idx;
		}
	});

	if (grnColIndex < 0 && typeof datatable.datamanager.getColumnIndexById === "function") {
		grnColIndex = datatable.datamanager.getColumnIndexById("grn_no");
	}
	if (entryColIndex < 0 && typeof datatable.datamanager.getColumnIndexById === "function") {
		entryColIndex = datatable.datamanager.getColumnIndexById("entry");
	}
	if (rowIndexColIndex < 0 && typeof datatable.datamanager.getColumnIndexById === "function") {
		rowIndexColIndex = datatable.datamanager.getColumnIndexById("_rowIndex");
	}
	if (lastGrnColIndex < 0 && typeof datatable.datamanager.getColumnIndexById === "function") {
		lastGrnColIndex = datatable.datamanager.getColumnIndexById("net_weight");
	}

	const lastSummaryColIndex = summaryColIndices.length ? Math.max(...summaryColIndices) : -1;
	const lastEntryColIndex = entryColIndices.length ? Math.max(...entryColIndices) : -1;

	const slipNoColIndex = datatable.datamanager.getColumnIndexById("ppc_name_slip_no");

	inject_mandi_book_styles(group_end_indices, {
		slipNoColIndex,
		grnColIndex,
		entryColIndex,
		rowIndexColIndex,
		lastSummaryColIndex,
		lastEntryColIndex,
		lastGrnColIndex,
		summaryColIndices,
		entryColIndices,
		grnColIndices
	});

	if (datatable.wrapper) {
		const oldEnds = datatable.wrapper.querySelectorAll(".mandi-book-group-end");
		if (oldEnds) {
			oldEnds.forEach((el) => el.classList.remove("mandi-book-group-end"));
		}
		group_end_indices.forEach((idx) => {
			const $row = datatable.wrapper.querySelector(`.dt-row-${idx}`);
			if ($row) {
				$row.classList.add("mandi-book-group-end");
			}
		});
	}

	if (!datatable._applying_mandi_grouping && datatable.renderBody) {
		try {
			datatable._applying_mandi_grouping = true;
			datatable.renderBody();
		} finally {
			datatable._applying_mandi_grouping = false;
		}
	}

	if (!datatable._mandi_sort_listener_attached && datatable.on) {
		datatable._mandi_sort_listener_attached = true;
		datatable.on("onSortColumn", () => {
			apply_mandi_book_grouping(datatable);
		});
		datatable.on("onSwitchColumn", () => {
			apply_mandi_book_grouping(datatable);
		});
	}
}

function inject_mandi_book_styles(group_end_indices, col_indices = {}) {
	let style = document.getElementById("mandi-book-group-styles");
	if (!style) {
		style = document.createElement("style");
		style.id = "mandi-book-group-styles";
		document.head.appendChild(style);
	}

	let group_border_css = "";
	if (group_end_indices && group_end_indices.length > 0) {
		const selectors = group_end_indices
			.map((idx) => `.report-wrapper .dt-row-${idx} .dt-cell, .datatable .dt-row-${idx} .dt-cell`)
			.join(",\n\t\t");
		group_border_css = `
		.report-wrapper .mandi-book-group-end .dt-cell,
		.datatable .mandi-book-group-end .dt-cell,
		${selectors} {
			border-bottom: 2px solid var(--gray-600, #4c5a67) !important;
		}
		`;
	}

	let vertical_border_css = "";
	const rowIndexCol = col_indices.rowIndexColIndex != null ? col_indices.rowIndexColIndex : -1;
	const lastSummaryCol = col_indices.lastSummaryColIndex != null ? col_indices.lastSummaryColIndex : -1;
	const lastEntryCol = col_indices.lastEntryColIndex != null ? col_indices.lastEntryColIndex : -1;
	const lastGrnCol = col_indices.lastGrnColIndex != null ? col_indices.lastGrnColIndex : -1;

	const slipNoCol = col_indices.slipNoColIndex != null ? col_indices.slipNoColIndex : -1;
	if (slipNoCol >= 0) {
		vertical_border_css += `
		.report-wrapper .dt-cell--col-${slipNoCol},
		.datatable .dt-cell--col-${slipNoCol} {
			border-right: 2px solid var(--gray-600, #4c5a67) !important;
		}
		`;
	}

	if (rowIndexCol >= 0) {
		vertical_border_css += `
		.report-wrapper .dt-cell--col-${rowIndexCol},
		.datatable .dt-cell--col-${rowIndexCol} {
			border-right: 2px solid var(--gray-600, #4c5a67) !important;
		}
		`;
	}

	if (lastSummaryCol >= 0) {
		vertical_border_css += `
		.report-wrapper .dt-cell--col-${lastSummaryCol},
		.datatable .dt-cell--col-${lastSummaryCol} {
			border-right: 2px solid var(--gray-600, #4c5a67) !important;
		}
		`;
	}

	if (lastEntryCol >= 0) {
		vertical_border_css += `
		.report-wrapper .dt-cell--col-${lastEntryCol},
		.datatable .dt-cell--col-${lastEntryCol} {
			border-right: 2px solid var(--gray-600, #4c5a67) !important;
		}
		`;
	}

	if (lastGrnCol >= 0) {
		vertical_border_css += `
		.report-wrapper .dt-cell--col-${lastGrnCol},
		.datatable .dt-cell--col-${lastGrnCol} {
			border-right: 2px solid var(--gray-600, #4c5a67) !important;
		}
		`;
	}

	let section_header_colors_css = "";
	const summaryCols = col_indices.summaryColIndices || [];
	const entryCols = col_indices.entryColIndices || [];
	const grnCols = col_indices.grnColIndices || [];

	if (summaryCols.length > 0) {
		const sel = summaryCols
			.map((i) => `.report-wrapper .dt-header .dt-cell--col-${i}, .report-wrapper .dt-header .dt-cell--col-${i} .dt-cell__content`)
			.join(",\n\t\t");
		section_header_colors_css += `
		${sel} {
			background-color: #eff6ff !important;
			color: #1e293b !important;
		}
		`;
	}

	if (entryCols.length > 0) {
		const sel = entryCols
			.map((i) => `.report-wrapper .dt-header .dt-cell--col-${i}, .report-wrapper .dt-header .dt-cell--col-${i} .dt-cell__content`)
			.join(",\n\t\t");
		section_header_colors_css += `
		${sel} {
			background-color: #f0fdf4 !important;
			color: #1e293b !important;
		}
		`;
	}

	if (grnCols.length > 0) {
		const sel = grnCols
			.map((i) => `.report-wrapper .dt-header .dt-cell--col-${i}, .report-wrapper .dt-header .dt-cell--col-${i} .dt-cell__content`)
			.join(",\n\t\t");
		section_header_colors_css += `
		${sel} {
			background-color: #fffbeb !important;
			color: #1e293b !important;
		}
		`;
	}

	if (rowIndexCol >= 0) {
		section_header_colors_css += `
		.report-wrapper .dt-header .dt-cell--col-${rowIndexCol},
		.report-wrapper .dt-header .dt-cell--col-${rowIndexCol} .dt-cell__content {
			background-color: #f8fafc !important;
			color: #64748b !important;
		}
		`;
	}

	style.textContent = `
		.report-wrapper .dt-cell--col-0,
		.datatable .dt-cell--col-0 {
			font-weight: 600;
		}
		.dt-row-super-header {
			display: flex;
			background-color: var(--dt-header-cell-bg, #f1f5f9);
			border-bottom: 2px solid var(--gray-600, #4c5a67) !important;
			min-height: 42px;
			box-sizing: border-box;
			width: max-content;
			min-width: 100%;
			margin: 0;
			padding: 0;
		}
		.dt-super-cell {
			border: 1px solid var(--dt-border-color, #cbd5e1);
			border-bottom: none !important;
			border-left: none;
			padding: 6px 10px;
			text-align: center;
			box-sizing: border-box;
			display: flex;
			flex-direction: column;
			justify-content: center;
			align-items: center;
			overflow: hidden;
			flex-shrink: 0;
			margin: 0;
		}
		.dt-super-cell:first-child {
			border-left: 1px solid var(--dt-border-color, #cbd5e1);
		}
		.dt-super-cell--spacer {
			background-color: #f1f5f9 !important;
			font-weight: 700;
			font-size: 12px;
			color: #475569 !important;
		}
		.dt-super-cell--row-index-divider {
			border-right: 2px solid var(--gray-600, #4c5a67) !important;
		}
		.dt-super-cell--summary {
			background-color: #dbeafe !important;
			color: #1e3a8a !important;
			border-right: 2px solid var(--gray-600, #4c5a67) !important;
		}
		.dt-super-cell--entry {
			background-color: #dcfce7 !important;
			color: #14532d !important;
			border-right: 2px solid var(--gray-600, #4c5a67) !important;
		}
		.dt-super-cell--grn {
			background-color: #fef3c7 !important;
			color: #78350f !important;
			border-right: 2px solid var(--gray-600, #4c5a67) !important;
		}
		.dt-super-cell-title {
			font-size: 13px;
			font-weight: 700;
			line-height: 1.3;
			letter-spacing: 0.5px;
			text-transform: uppercase;
			white-space: normal;
			word-wrap: break-word;
			overflow-wrap: break-word;
			text-align: center;
			width: 100%;
			max-width: 100%;
		}
		.report-wrapper .dt-row-header,
		.datatable .dt-row-header {
			border-top: none !important;
			margin: 0;
			padding: 0;
			height: auto !important;
			min-height: 38px !important;
		}
		.report-wrapper .dt-row-header .dt-cell--header,
		.datatable .dt-row-header .dt-cell--header {
			border-top: none !important;
			height: auto !important;
			min-height: 38px !important;
			display: flex !important;
			align-items: center !important;
		}
		.report-wrapper .dt-header .dt-cell--header .dt-cell__content {
			white-space: normal !important;
			word-break: normal !important;
			overflow-wrap: break-word !important;
			text-overflow: unset !important;
			line-height: 1.25 !important;
			font-size: 12px !important;
			font-weight: 600 !important;
			padding: 4px 10px 4px 6px !important;
			display: flex !important;
			align-items: center !important;
			height: 100% !important;
		}
		.report-wrapper .dt-header .dt-cell--header .dt-dropdown {
			position: absolute !important;
			right: 4px !important;
			top: 50% !important;
			transform: translateY(-50%) !important;
		}
		${group_border_css}
		${vertical_border_css}
		${section_header_colors_css}
	`;
}

function render_mandi_book_super_header(datatable_obj) {
	if (!datatable_obj || !datatable_obj.header || !datatable_obj.datamanager) return;
	if (datatable_obj._super_header_rendering) return;

	const $ = window.jQuery || (typeof jQuery !== "undefined" ? jQuery : null);
	if (!$) return;

	const $headerRow = $(datatable_obj.header).find(".dt-row-header");
	if (!$headerRow.length) return;

	const columns = datatable_obj.datamanager.getColumns();
	if (!columns || !columns.length) return;

	datatable_obj._super_header_rendering = true;
	try {
		let $superHeader = $(datatable_obj.header).find(".dt-row-super-header");
		if (!$superHeader.length) {
			$superHeader = $('<div class="dt-row dt-row-super-header"></div>');
			$headerRow.before($superHeader);
		}
		$superHeader.empty();

		const getHeaderCell = (col) => {
			if (!col) return null;
			const colIndex = col.colIndex != null ? col.colIndex : -1;
			if (colIndex < 0) return null;
			return (
				$headerRow.find(`.dt-cell--col-${colIndex}`)[0] ||
				$headerRow.find(`.dt-cell--header-${colIndex}`)[0]
			);
		};

		const getGroupWidth = (startCol, endCol, fallbackSum) => {
			const startEl = getHeaderCell(startCol);
			const endEl = getHeaderCell(endCol);
			if (startEl && endEl && endEl.offsetWidth > 0) {
				const startLeft = startEl.offsetLeft;
				const endRight = endEl.offsetLeft + endEl.offsetWidth;
				const measuredWidth = endRight - startLeft;
				if (measuredWidth > 0) {
					return measuredWidth;
				}
			}
			return fallbackSum;
		};

		const getColWidth = (col) => {
			if (!col) return 0;
			const cellEl = getHeaderCell(col);
			if (cellEl && cellEl.offsetWidth > 0) {
				return cellEl.offsetWidth;
			}
			const baseW = parseFloat(col.width) || 120;
			return col.colIndex === 0 ? baseW + 2 : baseW + 1;
		};

		const toPx = (val) => `${Number(val).toFixed(2)}px`;

		const lastCol = columns[columns.length - 1];
		const lastCellEl = getHeaderCell(lastCol);
		let totalRowWidth = 0;
		if (lastCellEl && lastCellEl.offsetWidth > 0) {
			totalRowWidth = lastCellEl.offsetLeft + lastCellEl.offsetWidth;
		} else if ($headerRow[0]) {
			totalRowWidth = $headerRow[0].scrollWidth || $headerRow.outerWidth();
		}
		if (totalRowWidth > 0) {
			$superHeader.css({
				"width": totalRowWidth + "px",
				"min-width": totalRowWidth + "px",
				"max-width": totalRowWidth + "px"
			});
		}

		const summaryFieldnames = new Set([
			"season",
			"ppc_name_slip_no",
			"ppc_name",
			"rst_no",
			"mill_name",
			"transit_pass_no",
			"pass_unique_key",
			"tp_quantity",
			"total_gross_weight",
			"total_other_tp_qty",
			"summary_gunny_type",
			"total_gunny_weight",
			"total_deduction_received",
			"chhatni_received_qty",
			"total_received",
			"pending_qty",
			"excess_received_qty",
			"tp_status",
			"jute_pkt",
			"plastic_pkt",
			"total_bags",
			"chhatni_assigned",
			"actual_chhatni_pct",
			"chhatni_status"
		]);

		const entryFieldnames = new Set([
			"entry",
			"agent_name",
			"entry_quantity",
			"entry_price_per_quintal",
			"total_amount"
		]);

		const grnFieldnames = new Set([
			"grn_no",
			"rst_no",
			"vehicle_no",
			"load_weight",
			"tare_weight",
			"gross_weight",
			"other_tp_qty",
			"gunny_type",
			"gunny_weight",
			"deduction",
			"net_weight"
		]);

		let i = 0;
		while (i < columns.length) {
			const col = columns[i];
			const fieldname = col.id || col.fieldname || "";

			if (fieldname === "_rowIndex") {
				const width = getColWidth(col);
				const $cell = $(`
					<div class="dt-super-cell dt-super-cell--spacer dt-super-cell--row-index-divider"
						style="width: ${toPx(width)}; min-width: ${toPx(width)}; max-width: ${toPx(width)}; flex: 0 0 ${toPx(width)};">
						<div class="dt-super-cell-title">#</div>
					</div>
				`);
				$superHeader.append($cell);
				i++;
			} else if (summaryFieldnames.has(fieldname)) {
				let startCol = null;
				let endCol = null;
				let fallbackSum = 0;

				while (i < columns.length && summaryFieldnames.has(columns[i].id || columns[i].fieldname || "")) {
					const c = columns[i];
					if (!c.hidden) {
						if (!startCol) startCol = c;
						endCol = c;
						fallbackSum += (parseFloat(c.width) || 120) + 1;
					}
					i++;
				}

				const totalWidth = getGroupWidth(startCol, endCol, fallbackSum);
				const $cell = $(`
					<div class="dt-super-cell dt-super-cell--summary" title="${__("Summary")}"
						style="width: ${toPx(totalWidth)}; min-width: ${toPx(totalWidth)}; max-width: ${toPx(totalWidth)}; flex: 0 0 ${toPx(totalWidth)};">
						<div class="dt-super-cell-title">${__("Summary")}</div>
					</div>
				`);
				$superHeader.append($cell);
			} else if (entryFieldnames.has(fieldname)) {
				let startCol = null;
				let endCol = null;
				let fallbackSum = 0;

				while (i < columns.length && entryFieldnames.has(columns[i].id || columns[i].fieldname || "")) {
					const c = columns[i];
					if (!c.hidden) {
						if (!startCol) startCol = c;
						endCol = c;
						fallbackSum += (parseFloat(c.width) || 120) + 1;
					}
					i++;
				}

				const totalWidth = getGroupWidth(startCol, endCol, fallbackSum);
				const $cell = $(`
					<div class="dt-super-cell dt-super-cell--entry" title="${__("Entry Details")}"
						style="width: ${toPx(totalWidth)}; min-width: ${toPx(totalWidth)}; max-width: ${toPx(totalWidth)}; flex: 0 0 ${toPx(totalWidth)};">
						<div class="dt-super-cell-title">${__("Entry Details")}</div>
					</div>
				`);
				$superHeader.append($cell);
			} else if (grnFieldnames.has(fieldname)) {
				let startCol = null;
				let endCol = null;
				let fallbackSum = 0;

				while (i < columns.length && grnFieldnames.has(columns[i].id || columns[i].fieldname || "")) {
					const c = columns[i];
					if (!c.hidden) {
						if (!startCol) startCol = c;
						endCol = c;
						fallbackSum += (parseFloat(c.width) || 120) + 1;
					}
					i++;
				}

				const totalWidth = getGroupWidth(startCol, endCol, fallbackSum);
				const $cell = $(`
					<div class="dt-super-cell dt-super-cell--grn" title="${__("GRN Details")}"
						style="width: ${toPx(totalWidth)}; min-width: ${toPx(totalWidth)}; max-width: ${toPx(totalWidth)}; flex: 0 0 ${toPx(totalWidth)};">
						<div class="dt-super-cell-title">${__("GRN Details")}</div>
					</div>
				`);
				$superHeader.append($cell);
			} else {
				const width = getColWidth(col);
				const $cell = $(`
					<div class="dt-super-cell dt-super-cell--spacer"
						style="width: ${toPx(width)}; min-width: ${toPx(width)}; max-width: ${toPx(width)}; flex: 0 0 ${toPx(width)};"></div>
				`);
				$superHeader.append($cell);
				i++;
			}
		}
	} finally {
		datatable_obj._super_header_rendering = false;
	}

	if (!datatable_obj.__mandi_header_bound) {
		datatable_obj.__mandi_header_bound = true;
		$(window).off("resize.mandi_book").on("resize.mandi_book", () => {
			render_mandi_book_super_header(datatable_obj);
		});
	}
	if (!datatable_obj.__mandi_resize_observer && typeof ResizeObserver !== "undefined" && $headerRow[0]) {
		const ro = new ResizeObserver(() => {
			render_mandi_book_super_header(datatable_obj);
		});
		ro.observe($headerRow[0]);
		datatable_obj.__mandi_resize_observer = ro;
	}
	if (!datatable_obj.__mandi_events_bound && datatable_obj.on) {
		datatable_obj.__mandi_events_bound = true;
		datatable_obj.on("onSortColumn", () => render_mandi_book_super_header(datatable_obj));
		datatable_obj.on("onSwitchColumn", () => render_mandi_book_super_header(datatable_obj));
	}
}

function mandi_book_status_pill(value) {
	const text = value == null || value === "" ? "" : String(value);
	let indicator = "gray";
	if (text === "Chhatni Received") {
		indicator = "green";
	} else if (text === "Extra Chhatni Received" || text === "Over Filled Chhatni Received") {
		indicator = "blue";
	} else if (text === "Chhatni Not Received") {
		indicator = "orange";
	} else if (text === "Chhatni Pending") {
		indicator = "yellow";
	}
	return `<span class="indicator-pill ${indicator}">${frappe.utils.escape_html(text)}</span>`;
}

function mandi_book_dialog(kind, data) {
	const is_grn = kind === "grn" || kind === "rst";
	const lines = is_grn ? (data.grn_lines || data.rst_lines || []) : (data.entry_lines || []);
	const tp_no = data.transit_pass_no || "";
	const title = is_grn ? __("GRN Details — TP {0}", [tp_no]) : __("Entry Details — TP {0}", [tp_no]);
	const dialog = new frappe.ui.Dialog({
		title,
		size: "extra-large",
		fields: [{ fieldtype: "HTML", fieldname: "details" }],
	});
	dialog.fields_dict.details.$wrapper.html(mandi_book_table(kind, lines));
	dialog.show();
}

function mandi_book_table(kind, lines) {
	if (kind === "grn" || kind === "rst") {
		return mandi_book_html_table(
			[
				__("GRN No."),
				__("Rst No."),
				__("Vehicle No."),
				__("Load Wt"),
				__("Tare Wt"),
				__("Gross Wt"),
				__("Other TP Qty"),
				__("Gunny Type"),
				__("Gunny Wt"),
				__("Deduction"),
				__("Net Wt"),
			],
			lines.map((line) => [
				mandi_book_doc_link("GRN Note", line.grn_name, line.grn_no || line.grn_name),
				line.rst_no
					? (line.weigh_bridge_measurement
						? mandi_book_doc_link("Weigh Bridge Measurement", line.weigh_bridge_measurement, line.rst_no)
						: frappe.utils.escape_html(line.rst_no))
					: (line.weigh_bridge_measurement
						? mandi_book_doc_link("Weigh Bridge Measurement", line.weigh_bridge_measurement)
						: "—"),
				frappe.utils.escape_html(line.vehicle_no || line.actual_vehicle_no || "—"),
				mandi_book_qty(line.load_weight, 3),
				mandi_book_qty(line.tare_weight, 3),
				mandi_book_qty(line.gross_weight, 3),
				flt(line.other_tp_qty) > 0 ? mandi_book_qty(line.other_tp_qty, 3) : "—",
				frappe.utils.escape_html(line.gunny_type || "—"),
				mandi_book_qty(line.gunny_weight, 3),
				mandi_book_qty(line.deduction, 3),
				mandi_book_qty(line.net_weight, 3),
			]),
			__("No GRN on this TP")
		);
	}
	return mandi_book_html_table(
		[__("Entry"), __("Agent Name"), __("Quantity"), __("Price per Quintal"), __("Total Amount")],
		lines.map((line) => [
			mandi_book_doc_link("Entry", line.entry),
			frappe.utils.escape_html(line.agent_name || "—"),
			mandi_book_qty(line.entry_quantity, 3),
			mandi_book_qty(line.entry_price_per_quintal, 2),
			mandi_book_qty(line.total_amount, 2),
		]),
		__("No Entry on this TP")
	);
}

function mandi_book_html_table(headers, body, empty_text) {
	if (!body.length) {
		return `<div class="text-muted" style="padding:8px 4px;">${frappe.utils.escape_html(empty_text)}</div>`;
	}
	const head = headers.map((label) => `<th>${frappe.utils.escape_html(label)}</th>`).join("");
	const rows = body
		.map((cells) => `<tr>${cells.map((cell) => `<td>${cell}</td>`).join("")}</tr>`)
		.join("");
	return `<div style="overflow:auto;"><table class="table table-bordered table-sm" style="margin-bottom:0;"><thead><tr>${head}</tr></thead><tbody>${rows}</tbody></table></div>`;
}

function mandi_book_doc_link(doctype, name, label) {
	if (!name) {
		return "—";
	}
	const display = label || name;
	const route = frappe.utils.get_form_link(doctype, name);
	return `<a href="${route}">${frappe.utils.escape_html(display)}</a>`;
}

function mandi_book_qty(value, precision) {
	const number = flt(value);
	return frappe.utils.escape_html(number.toFixed(precision));
}
