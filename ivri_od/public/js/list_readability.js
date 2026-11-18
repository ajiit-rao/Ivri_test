// List views of this app (Procurement, Bag Management): every column is wide enough for its heading
// and a normal value, and long text wraps onto a second line instead of being cut with "...".
// A width already set for a column (by a list script of that DocType, or dragged by the user and saved)
// is kept. List views of other apps are not changed. Display only: nothing is saved.
(function () {
	const APP = "ivri_od";
	const MIN_WIDTH = 70;
	const MAX_WIDTH = 400;
	// Room around the heading text: cell padding and the sort button.
	const HEADER_PADDING = 44;

	// Width in pixels that fits a normal value of the field type.
	const TYPE_WIDTH = {
		Date: 120,
		Datetime: 160,
		Time: 100,
		Int: 110,
		Float: 120,
		Currency: 130,
		Percent: 110,
		Check: 90,
		Select: 140,
		Link: 190,
		"Dynamic Link": 190,
		Data: 170,
		Phone: 150,
		Autocomplete: 170,
	};
	const DEFAULT_WIDTH = 170;

	let canvas;
	function text_width(text, bold) {
		canvas = canvas || document.createElement("canvas");
		const ctx = canvas.getContext("2d");
		const style = getComputedStyle(document.body);
		ctx.font = `${bold ? "600 " : ""}${style.fontSize} ${style.fontFamily}`;
		return ctx.measureText(text || "").width;
	}

	function is_app_doctype(doctype) {
		const meta = frappe.get_meta(doctype);
		const module = meta && meta.module;
		return !!module && (frappe.boot.module_app || {})[frappe.scrub(module)] === APP;
	}

	function fit_columns(listview) {
		(listview.columns || []).forEach((col) => {
			const df = col.df;
			if (!df || !df.fieldname || cint(df.width)) return;
			if (col.type !== "Field" && col.type !== "Subject") return;

			const by_type = TYPE_WIDTH[df.fieldtype] || DEFAULT_WIDTH;
			const by_heading = text_width(__(df.label || ""), true) + HEADER_PADDING;
			const width = Math.round(Math.min(Math.max(by_type, by_heading, MIN_WIDTH), MAX_WIDTH));
			// Copy the field so the width is used in the list only.
			col.df = Object.assign({}, df, { width });
		});
	}

	function patch_list_view() {
		const ListView = frappe.views && frappe.views.ListView;
		if (!ListView) return false;
		if (ListView.prototype.__ivri_od_readability) return true;

		const setup_columns = ListView.prototype.setup_columns;
		ListView.prototype.setup_columns = async function () {
			const result = await setup_columns.apply(this, arguments);
			if (is_app_doctype(this.doctype)) {
				try {
					fit_columns(this);
					this.page.wrapper.addClass("ivri-list");
				} catch (e) {
					// The list is still drawn with its own columns.
					console.error(e);
				}
			}
			return result;
		};
		ListView.prototype.__ivri_od_readability = true;
		return true;
	}

	// The list bundle defines ListView; wait for it if this script runs first.
	if (!patch_list_view()) {
		const timer = setInterval(() => {
			if (patch_list_view()) clearInterval(timer);
		}, 50);
		setTimeout(() => clearInterval(timer), 10000);
	}
})();
