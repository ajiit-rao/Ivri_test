# Copyright (c) 2026, Profezzo and contributors
# For license information, please see license.txt

"""Requisition for DC from DCRO. DCRO portal, Delivery Certificate > Miller RQ PDS (Add page):
the mill's requisitions for DC, table "tabledata", read after Show. The agent opens the table
itself by clicking the + of dvmillerhistory (Portal Site Section "Auto Click Before Read").
KMS Year and Season are the page's #INTKMS and #ddlseason (Page Filter Columns).
District names as in Paddy Release from DCRO: "(Own District)" in a header is the mill's
District in Mill Master (e.g. Balangir), "(Other District)KORAPUT" is that District Master name
(Koraput); see procurement/dcro_paddy_release.py district_named_cells.
Data comes from Portal Data Extraction (agent) -> Portal Record; see procurement/portal_report.py."""

from ivri_od.procurement import dcro_filters
from ivri_od.procurement.dcro_paddy_release import district_named_cells
from ivri_od.procurement.portal_report import section_report

SECTION = "Requisition for DC"


def execute(filters=None):
	# Mill Name, KMS Year, Season (Both / Kharif / Rabi), District: shared DCRO filters (dcro_filters.py).
	keep = dcro_filters.row_filter(filters, "KMS Year", "Season", dcro_filters.district_in_headers())
	return section_report(filters, SECTION, site="DCRO", transform=district_named_cells, row_filter=keep)
