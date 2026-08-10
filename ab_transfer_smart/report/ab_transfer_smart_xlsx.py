# -*- coding: utf-8 -*-

import re

from odoo import _, models


class AbTransferSmartXlsx(models.AbstractModel):
    _name = "report.ab_transfer_smart.smart_transfer_xlsx"
    _inherit = "report.report_xlsx.abstract"
    _description = "Smart Transfer Excel Export"

    _HEADERS = (
        "code",
        "company",
        "purchase unit",
        "sell_price",
        "purchase_price",
        "source stock",
        "destination stock",
        "Sales 3 month",
        "moving weighted avg",
        "need",
    )

    def _get_translated_headers(self):
        return (
            _("code"),
            _("company"),
            _("purchase unit"),
            _("sell_price"),
            _("purchase_price"),
            _("source stock"),
            _("destination stock"),
            _("Sales 3 month"),
            _("moving weighted avg"),
            _("need"),
        )

    def generate_xlsx_report(self, workbook, data, headers):
        allow_incomplete = bool((data or {}).get("allow_incomplete_sales_cache"))
        header_format = workbook.add_format({
            "bold": True,
            "bg_color": "#D9EAF7",
            "border": 1,
            "align": "center",
            "valign": "vcenter",
        })
        text_format = workbook.add_format({"border": 1})
        number_format = workbook.add_format({"border": 1, "num_format": "0.000"})

        for header in headers:
            rows = header._get_smart_transfer_excel_rows(
                allow_incomplete_sales_cache=allow_incomplete
            )
            worksheet = workbook.add_worksheet(self._get_worksheet_name(header))
            worksheet.freeze_panes(1, 0)
            worksheet.autofilter(0, 0, max(len(rows), 1), len(self._HEADERS) - 1)
            worksheet.set_row(0, 24)

            for column_index, label in enumerate(self._get_translated_headers()):
                worksheet.write(0, column_index, label, header_format)

            for row_index, row in enumerate(rows, start=1):
                values = (
                    row["code"],
                    row["company"],
                    row["purchase_unit"],
                    row["sell_price"],
                    row["purchase_price"],
                    row["source_stock"],
                    row["destination_stock"],
                    row["sales_3_month"],
                    row["moving_weighted_avg"],
                    row["need"],
                )
                for column_index, value in enumerate(values):
                    cell_format = text_format if column_index < 2 else number_format
                    worksheet.write(row_index, column_index, value, cell_format)

            worksheet.set_column(0, 0, 16)
            worksheet.set_column(1, 1, 28)
            worksheet.set_column(2, len(self._HEADERS) - 1, 18)

    @staticmethod
    def _get_worksheet_name(header):
        store = header.to_store_id
        raw_name = " - ".join(
            part for part in (store.code, store.display_name) if part
        ) or "Smart Transfer"
        safe_name = re.sub(r"[\[\]:*?/\\]", "-", raw_name)
        safe_name = "".join(char for char in safe_name if ord(char) >= 32).strip()
        return (safe_name or "Smart Transfer")[:31]
