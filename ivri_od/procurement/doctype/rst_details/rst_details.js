// Copyright (c) 2026, Profezzo and contributors

function sync_mill_requirement(frm) {
	// Mill No is not mandatory while TP No is empty. It is fetched on save
	// only when Party Name is found and TP No is filled.
	frm.toggle_reqd("mill_name", false);
}

function refresh_tp_details(frm) {
	sync_mill_requirement(frm);
	const tp_no = (frm.doc.tp_no || "").trim();
	const party_name = (frm.doc.party_name || "").trim();
	// Only the reply for the latest TP No / Party Name may set the status.
	const request_id = (frm.__tp_details_request_id || 0) + 1;
	frm.__tp_details_request_id = request_id;

	frappe.call({
		method: "ivri_od.procurement.doctype.rst_details.rst_details.fetch_mill_and_agent_from_tp",
		args: {
			tp_no,
			party_name,
			entry_datetime: frm.doc.entry_datetime || "",
			commodity: frm.doc.commodity || "",
			transaction_type: frm.doc.transaction_type || "",
		},
		callback(r) {
			if (request_id !== frm.__tp_details_request_id) {
				return;
			}
			const data = r.message || {};
			if (data.tp_status !== undefined) {
				frm.set_value("tp_status", data.tp_status);
			}
			// Rice Dispatch and private deals ("Local ..."): keep the Mill No given on the RST.
			const keeps_mill = data.tp_status === "Rice Dispatch" || /^Local( |$)/.test(data.tp_status || "");
			if (data.mill_name !== undefined && !keeps_mill) {
				frm.set_value("mill_name", data.mill_name);
			}
			if (data.agent_name !== undefined) {
				frm.set_value("agent_name", data.agent_name);
			}
			for (const fieldname of ["season_code", "rst_unique_key", "tp_quantity"]) {
				if (data[fieldname] !== undefined && frm.fields_dict[fieldname]) {
					frm.set_value(fieldname, data[fieldname]);
				}
			}
			show_rst_unique_key_status(frm, data.key_message || "");
			if (data.notification) {
				frappe.msgprint({
					title: __(rst_status_label(data.tp_status, frm.doc) || "Status"),
					message: __(data.notification),
					indicator: "orange",
				});
			}
			if (data.validation_message) {
				frappe.msgprint({
					title: __("Transit Pass"),
					message: __(data.validation_message),
					indicator: "red",
				});
			}
			sync_mill_requirement(frm);
		},
	});
}

// Season Code and RST Unique Key are shown only when Party Name is a PPC (a Transit Pass party).
// Then they stay visible even when empty, so staff see they are empty. For a depo, a local
// farmer or a blank Party Name they are hidden.
function always_show_read_only(frm, fieldnames) {
	for (const fieldname of fieldnames) {
		const field = frm.fields_dict[fieldname];
		if (field && !field.df.get_status) {
			field.df.get_status = () =>
				frm.__party_is_ppc && frm.doc.tp_status !== "Rice Dispatch" ? "Read" : "None";
			field.refresh();
		}
	}
}

// Ask the server if Party Name is a PPC, then show or hide Season Code and RST Unique Key.
function sync_ppc_party_fields(frm, on_refresh = false) {
	const party_name = (frm.doc.party_name || "").trim();
	const request_id = (frm.__ppc_party_request_id || 0) + 1;
	frm.__ppc_party_request_id = request_id;
	const apply = (is_ppc) => {
		if (request_id !== frm.__ppc_party_request_id) {
			return;
		}
		frm.__party_is_ppc = Boolean(is_ppc);
		for (const fieldname of ["season_code", "rst_unique_key"]) {
			frm.refresh_field(fieldname);
		}
		if (!frm.__party_is_ppc) {
			frm.set_intro("");
		} else if (on_refresh) {
			// On load the key message ran before this answer came, so show it now.
			show_rst_unique_key_status(frm);
		}
	};
	if (!party_name) {
		apply(false);
		return;
	}
	frappe.call({
		method: "ivri_od.procurement.doctype.rst_details.rst_details.is_ppc_party",
		args: { party_name },
		callback(r) {
			apply(r.message);
		},
	});
}

// Say why the key is missing.
// message: the server's reason after a lookup; undefined on load, when the saved values decide.
function show_rst_unique_key_status(frm, message) {
	frm.set_intro("");
	if (!frm.fields_dict.rst_unique_key || frm.doc.tp_status === "Rice Dispatch" || !frm.__party_is_ppc) {
		return;
	}
	if (message === undefined && !frm.is_new() && !frm.doc.rst_unique_key) {
		if (!frm.doc.season_code) {
			message = __(
				"Season Not Configured. No Season Master has a Start Date - End Date range that covers this RST Date & Time. Set the season dates, then save this RST again."
			);
		} else if (frm.doc.tp_status === "TP Received") {
			message = __(
				"The Transit Pass for this TP No and PPC is not in season {0} of the RST Date & Time. Check the RST Date & Time or the Season Master dates.",
				[frm.doc.season_code]
			);
		}
	}
	if (message) {
		frm.set_intro(__("RST Unique Key is empty: {0}", [message]), "orange");
	}
}

// Hidden, for future RST-based Chhatni entry. Same rules as chhatni_from_rate on the server,
// which calculates these again on save. Not used by Mandi Book yet.
function calculate_rst_chhatni(frm) {
	if (!frm.fields_dict.chhatni_qt) {
		return;
	}
	const net_weight = flt(frm.doc.net_paddy_weight_qt, 3);
	const tp_quantity = flt(frm.doc.tp_quantity);
	let chhatni_kg = 0;
	let chhatni_qt = 0;
	let received_pct = 0;
	if (net_weight > 0) {
		chhatni_kg = flt(net_weight * flt(frm.doc.chhatni_kg_per_qtl), 3);
		chhatni_qt = flt(chhatni_kg / 100, 3);
		received_pct = tp_quantity > 0 ? flt((chhatni_qt / tp_quantity) * 100, 2) : 0;
	}
	frm.set_value({ chhatni_kg, chhatni_qt, received_chhatni_pct: received_pct });
}

// Party Name drop-down: PPCs of PPAS Transit Pass and Depo Master names. Typing another name
// (a local farmer) is still allowed, so the field never rejects a value.
function load_party_name_choices(frm) {
	const field = frm.fields_dict.party_name;
	if (!field) {
		return;
	}
	field.df.ignore_validation = 1;
	if (frappe.ivri_od_party_choices) {
		field.set_data(frappe.ivri_od_party_choices);
		return;
	}
	frappe.call({
		method: "ivri_od.procurement.doctype.rst_details.rst_details.get_party_name_choices",
		callback(r) {
			frappe.ivri_od_party_choices = r.message || [];
			field.set_data(frappe.ivri_od_party_choices);
		},
	});
}

// Party Name is a depo -> saved status "Rice Dispatch". Staff see "Rice Delivery to Depo", or
// "Lot No is empty" while TP No (shown as Lot No) is blank. Only the display changes: the saved
// value stays "Rice Dispatch" (the weighment, Rice Dispatch report and filters use it).
const RICE_DISPATCH = "Rice Dispatch";
const LOT_NO_EMPTY = "Lot No is empty";

function rst_status_label(value, doc) {
	if (value === RICE_DISPATCH) {
		return (doc?.tp_no || "").trim() ? "Rice Delivery to Depo" : LOT_NO_EMPTY;
	}
	return value || "";
}

function format_rst_status(value, doc) {
	const label = rst_status_label(value, doc);
	const html = frappe.utils.escape_html(__(label));
	return label === LOT_NO_EMPTY ? `<span class="text-danger">${html}</span>` : html;
}

// Depo RST: the TP No field holds the Lot No, so it is labelled Lot No, and Season Code and
// RST Unique Key are hidden (see always_show_read_only).
function sync_lot_no_label(frm) {
	const is_depo = frm.doc.tp_status === RICE_DISPATCH;
	frm.set_df_property("tp_no", "label", is_depo ? __("Lot No") : __("TP No"));
	for (const fieldname of ["tp_status", "season_code", "rst_unique_key"]) {
		frm.refresh_field(fieldname);
	}
	if (is_depo) {
		frm.set_intro("");
	}
}

frappe.ui.form.on("RST Details", {
	setup(frm) {
		const df = frm.get_docfield("tp_status");
		if (df) {
			df.formatter = (value, _df, _options, doc) => format_rst_status(value, doc || frm.doc);
		}
	},
	tp_status(frm) {
		sync_lot_no_label(frm);
	},
	refresh(frm) {
		sync_lot_no_label(frm);
		load_party_name_choices(frm);
		sync_mill_requirement(frm);
		frm.toggle_display("local_purchase_order", Boolean(frm.doc.local_purchase_order));
		always_show_read_only(frm, ["season_code", "rst_unique_key"]);
		show_rst_unique_key_status(frm);
		sync_ppc_party_fields(frm, true);
	},
	tp_no(frm) {
		frm.refresh_field("tp_status");
		refresh_tp_details(frm);
	},
	entry_datetime(frm) {
		refresh_tp_details(frm);
	},
	party_name(frm) {
		sync_ppc_party_fields(frm);
		refresh_tp_details(frm);
	},
	// Private deal status is "Local {Commodity} {Transaction Type}".
	commodity(frm) {
		refresh_tp_details(frm);
	},
	transaction_type(frm) {
		refresh_tp_details(frm);
	},
	net_paddy_weight_qt(frm) {
		calculate_rst_chhatni(frm);
	},
	chhatni_kg_per_qtl(frm) {
		calculate_rst_chhatni(frm);
	},
	tp_quantity(frm) {
		calculate_rst_chhatni(frm);
	},
	jute_bags(frm) {
		calculate_total_bags(frm);
	},
	plastic_bags(frm) {
		calculate_total_bags(frm);
	},
	old_bags(frm) {
		calculate_total_bags(frm);
	},
});

// Total Bags = Jute Bags + Plastic Bags + Old Bags (the server saves the same total).
function calculate_total_bags(frm) {
	const total = ["jute_bags", "plastic_bags", "old_bags"].reduce(
		(sum, fieldname) => sum + cint(frm.doc[fieldname]),
		0
	);
	frm.set_value("total_bags", total);
}
