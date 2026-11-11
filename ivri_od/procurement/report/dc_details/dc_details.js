// Copyright (c) 2026, Profezzo and contributors

// One line per mill for a season: rice due (CMR) and lots issued / delivered to FCI and RRC.
// Balance columns are highlighted as in the DC Details sheet; the last line is the total.
// Charts above the table are drawn from the report rows (see render_charts).
frappe.provide("ivri_od.dc_details");

const DC_DETAILS_HIGHLIGHT = ["fci_balance", "fci_pending", "rrc_balance", "rrc_pending", "vr_pending"];

// Clickable pending columns: fieldname -> kind sent to get_pending_lots.
const DC_DETAILS_PENDING = { fci_pending: "fci", rrc_pending: "rrc" };

frappe.query_reports["DC Details"] = {
	filters: [
		{ fieldname: "season", label: __("Season"), fieldtype: "Link", options: "Season Master", reqd: 1 },
		{ fieldname: "mill", label: __("Mill No."), fieldtype: "Link", options: "Mill Master" },
		{
			fieldname: "district",
			label: __("District"),
			fieldtype: "Link",
			options: "District Master",
			get_query: () => ({ filters: { is_active: 1 } }),
			description: __("DCs by District in View DC from DCRO; paddy by PPC's District. Empty: every district."),
		},
	],
	after_refresh(report) {
		ivri_od.dc_details.render_charts(report);
	},
	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (!data) return value;
		if (DC_DETAILS_HIGHLIGHT.includes(column.fieldname) && data[column.fieldname] > 0) {
			value = `<span class="indicator-pill yellow">${value}</span>`;
		}
		// FCI / RRC Pending: a click opens the pending lots (Total line: every mill).
		if (DC_DETAILS_PENDING[column.fieldname] && data[column.fieldname] > 0) {
			const kind = DC_DETAILS_PENDING[column.fieldname];
			const mill = data.is_total_row ? "" : frappe.utils.escape_html(data.mill || "");
			value = `<a href="#" title="${__("Show pending lots")}"
				onclick="ivri_od.dc_details.show_pending('${kind}', '${mill}'); return false;">${value}</a>`;
		}
		return data.is_total_row ? `<b>${value}</b>` : value;
	},
};

// Pending lots of one mill (or every mill when mill is ""), as counted in FCI / RRC Pending:
// FCI - DCRO DC Transit Challan rows not Approved and with no Accepted Date;
// RRC - SCMS Transit Challan RRC lots not in SCMS Lot Search yet. See get_pending_lots in dc_details.py.
ivri_od.dc_details.show_pending = function (kind, mill) {
	const report = frappe.query_report;
	frappe
		.xcall("ivri_od.procurement.report.dc_details.dc_details.get_pending_lots", {
			season: report.get_filter_value("season"),
			kind,
			mill: mill || null,
			district: report.get_filter_value("district") || null,
		})
		.then((r) => {
			const esc = frappe.utils.escape_html;
			const headers = [];
			r.lots.forEach((lot) => Object.keys(lot.cells).forEach((h) => !headers.includes(h) && headers.push(h)));
			const body = r.lots
				.map(
					(lot) => `<tr>
						<td>${esc(lot.mill)}</td><td>${esc(lot.dc_no)}</td><td>${esc(lot.lot_no)}</td>
						${headers.map((h) => `<td>${esc(lot.cells[h] || "")}</td>`).join("")}
					</tr>`
				)
				.join("");
			const html = `
				<p>${__("Source")}: <b>${esc(r.source)}</b> &nbsp; ${__("Pending Lots")}: <b>${r.lots.length}</b></p>
				<div style="overflow-x: auto">
					<table class="table table-bordered table-sm">
						<thead><tr>
							<th>${__("Mill No.")}</th><th>${__("DC No.")}</th><th>${__("Lot No.")}</th>
							${headers.map((h) => `<th>${esc(h)}</th>`).join("")}
						</tr></thead>
						<tbody>${body || `<tr><td colspan="3" class="text-muted">${__("No pending lots")}</td></tr>`}</tbody>
					</table>
				</div>`;
			const dialog = new frappe.ui.Dialog({
				title: mill
					? __("{0} Pending Lots of {1}", [r.kind, mill])
					: __("{0} Pending Lots of All Mills", [r.kind]),
				size: "extra-large",
				fields: [{ fieldtype: "HTML", fieldname: "lots" }],
			});
			dialog.fields_dict.lots.$wrapper.html(html);
			dialog.show();
		});
};

// ---------------------------------------------------------------
// Charts: lot status of the season (donut), lot status per mill (stacked bar)
// and Delivery % per mill (bar)
// ---------------------------------------------------------------

// Categorical slots 1-3 (blue, orange, aqua), checked for colour-blind separation;
// own steps in dark mode. Delivery % is one series: slot 1 only.
const DC_DETAILS_COLOURS = {
	light: ["#2a78d6", "#eb6834", "#1baf7a"],
	dark: ["#3987e5", "#d95926", "#199e70"],
};

ivri_od.dc_details.render_charts = function (report) {
	report.page.main.find(".dc-details-charts").remove();
	// The total line is not a mill: left out of the charts.
	const mills = (report.data || []).filter((r) => !r.is_total_row);
	if (!mills.length || typeof frappe.Chart === "undefined") {
		return;
	}
	const $panel = $(`
		<div class="dc-details-charts" style="display: flex; flex-wrap: wrap; gap: 16px; margin: 0 0 16px;">
			<div class="frappe-card" style="flex: 1 1 300px; min-width: 0; padding: 12px;">
				<div class="text-muted small">${__("Lot Status, All Mills")}</div>
				<div class="dc-details-status"></div>
			</div>
			<div class="frappe-card" style="flex: 2 1 480px; min-width: 0; padding: 12px;">
				<div class="text-muted small">${__("Lot Status per Mill (bar height = Total Lot)")}</div>
				<div class="dc-details-lots"></div>
			</div>
			<div class="frappe-card" style="flex: 1 1 320px; min-width: 0; padding: 12px;">
				<div class="text-muted small">${__("Delivery % per Mill")}</div>
				<div class="dc-details-percent"></div>
			</div>
		</div>`);
	$panel.insertBefore(report.$report);

	const dark = document.documentElement.getAttribute("data-theme") === "dark";
	const colours = DC_DETAILS_COLOURS[dark ? "dark" : "light"];
	// Short labels on the axis: the mill name without "(Boiled)" / "(Raw)", plus the type.
	const labels = mills.map((r) => `${(r.mill_name || r.mill).replace(/\s*\(.*\)\s*$/, "")} ${r.mill_type || ""}`.trim());

	// Total Lot split in three: delivered, issued but not delivered, not issued yet.
	// The last two are Total DC Issued - Total Delivery and Total DC Issue Balance.
	const parts = [
		mills.map((r) => Math.max(r.total_delivery || 0, 0)),
		mills.map((r) => Math.max((r.total_dc_issued || 0) - (r.total_delivery || 0), 0)),
		mills.map((r) => Math.max(r.total_dc_issue_balance || 0, 0)),
	];
	const part_names = [__("Delivered"), __("Issued, Not Delivered"), __("Not Issued Yet")];

	// Donut: the same three parts added over all mills; a part with 0 lots is left out.
	const totals = parts.map((values) => values.reduce((a, b) => a + b, 0));
	const shown = [0, 1, 2].filter((i) => totals[i] > 0);
	if (shown.length) {
		new frappe.Chart($panel.find(".dc-details-status")[0], {
			type: "donut",
			height: 280,
			data: { labels: shown.map((i) => part_names[i]), datasets: [{ values: shown.map((i) => totals[i]) }] },
			colors: shown.map((i) => colours[i]),
			maxSlices: shown.length,
			tooltipOptions: { formatTooltipY: (v) => __("{0} lots", [v]) },
		});
	} else {
		$panel.find(".dc-details-status").html(`<p class="text-muted">${__("No lots to show")}</p>`);
	}

	new frappe.Chart($panel.find(".dc-details-lots")[0], {
		type: "bar",
		height: 280,
		data: {
			labels,
			datasets: parts.map((values, i) => ({ name: part_names[i], values })),
		},
		colors: colours,
		barOptions: { stacked: 1, spaceRatio: 0.4 },
		axisOptions: { xAxisMode: "tick", xIsSeries: 0 },
		tooltipOptions: { formatTooltipY: (v) => __("{0} lots", [v]) },
	});

	new frappe.Chart($panel.find(".dc-details-percent")[0], {
		type: "bar",
		height: 280,
		data: {
			labels,
			datasets: [{ name: __("Delivery %"), values: mills.map((r) => r.delivery_percent || 0) }],
		},
		colors: [colours[0]],
		barOptions: { spaceRatio: 0.4 },
		axisOptions: { xAxisMode: "tick" },
		tooltipOptions: { formatTooltipY: (v) => `${v}%` },
	});
};
