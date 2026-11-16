# Copyright (c) 2026, Profezzo and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class WeighmentOtherTP(Document):
	"""One other Transit Pass whose paddy came in the same truck (RST): its Qty is not this TP's."""
