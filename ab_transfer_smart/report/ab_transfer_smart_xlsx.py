# -*- coding: utf-8 -*-

import re

from odoo import _, models


class AbTransferSmartWizardXlsx(models.AbstractModel):
    _name = "report.ab_transfer_smart.smart_transfer_wizard_xlsx"
    _inherit = "report.report_xlsx.abstract"
    _description = "Smart Transfer Wizard Excel Export"

    _HEADERS = (
        "code",
        "product name",
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
            _("product name"),
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

    def generate_xlsx_report(self, workbook, data, wizards):
        allow_incomplete = bool((data or {}).get("allow_incomplete_sales_cache"))
        used_names = set()
        for wizard in wizards:
            wizard._validate_smart_export_values()
            for probe in wizard._get_smart_export_probe_headers():
                probe = probe.with_context(
                    smart_export_readonly=True,
                    skip_smart_sales_cache_coverage=allow_incomplete,
                )
                rows = probe._get_smart_transfer_excel_rows(
                    allow_incomplete_sales_cache=allow_incomplete,
                    allow_empty=True,
                )
                worksheet_name = self._get_unique_worksheet_name(
                    self._get_worksheet_name(probe),
                    used_names,
                )
                self._add_smart_transfer_worksheet(
                    workbook,
                    worksheet_name,
                    rows,
                )

    def _add_smart_transfer_worksheet(self, workbook, worksheet_name, rows):
        header_format = workbook.add_format({
            "bold": True,
            "bg_color": "#D9EAF7",
            "border": 1,
            "align": "center",
            "valign": "vcenter",
        })
        text_format = workbook.add_format({"border": 1})
        number_format = workbook.add_format({"border": 1, "num_format": "0.000"})

        worksheet = workbook.add_worksheet(worksheet_name)
        worksheet.freeze_panes(1, 0)
        worksheet.autofilter(0, 0, max(len(rows), 1), len(self._HEADERS) - 1)
        worksheet.set_row(0, 24)

        for column_index, label in enumerate(self._get_translated_headers()):
            worksheet.write(0, column_index, label, header_format)

        for row_index, row in enumerate(rows, start=1):
            values = (
                row["code"],
                row["product_name"],
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
                cell_format = text_format if column_index < 3 else number_format
                worksheet.write(row_index, column_index, value, cell_format)

        worksheet.set_column(0, 0, 16)
        worksheet.set_column(1, 1, 42)
        worksheet.set_column(2, 2, 28)
        worksheet.set_column(3, len(self._HEADERS) - 1, 18)
        return worksheet

    @staticmethod
    def _get_worksheet_name(header):
        store = header.to_store_id
        raw_name = " - ".join(
            part for part in (store.code, store.display_name) if part
        ) or "Smart Transfer"
        safe_name = re.sub(r"[\[\]:*?/\\]", "-", raw_name)
        safe_name = "".join(char for char in safe_name if ord(char) >= 32).strip()
        return (safe_name or "Smart Transfer")[:31]

    @staticmethod
    def _get_unique_worksheet_name(worksheet_name, used_names):
        worksheet_name = (worksheet_name or "Smart Transfer")[:31]
        candidate = worksheet_name
        suffix_number = 2
        while candidate.casefold() in used_names:
            suffix = " (%s)" % suffix_number
            candidate = "%s%s" % (worksheet_name[:31 - len(suffix)], suffix)
            suffix_number += 1
        used_names.add(candidate.casefold())
        return candidate
