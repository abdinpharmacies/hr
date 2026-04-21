import io

from odoo import http
from odoo.http import content_disposition, request


class AbQualityAssuranceVisitExportController(http.Controller):
    @http.route(
        "/ab_quality_assurance/visit/<int:visit_id>/xlsx",
        type="http",
        auth="user",
        methods=["GET"],
    )
    def download_visit_xlsx(self, visit_id, **kwargs):
        import xlsxwriter  # noqa: PLC0415

        visit = request.env["ab_quality_assurance_visit"].browse(visit_id).exists()
        if not visit:
            return request.not_found()

        visit.check_access("read")

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        visit._generate_xlsx_workbook(workbook)
        workbook.close()
        output.seek(0)

        filename = f"{visit._get_export_basename()}.xlsx"
        headers = [
            ("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
            ("Content-Disposition", content_disposition(filename)),
        ]
        return request.make_response(output.getvalue(), headers=headers)
