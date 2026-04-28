from odoo import fields, models


class AbQualityAssuranceDepartmentDashboard(models.Model):
    _name = "ab_quality_assurance_department_dashboard"
    _description = "Quality Assurance Department Dashboard"
    _auto = False
    _rec_name = "department_id"

    department_id = fields.Many2one("ab_hr_department", readonly=True)
    visit_count = fields.Integer(readonly=True)
    submitted_visit_count = fields.Integer(readonly=True)
    draft_visit_count = fields.Integer(readonly=True)
    avg_earned_score = fields.Float(readonly=True)
    avg_percentage = fields.Float(readonly=True)
    best_percentage = fields.Float(readonly=True)
    submission_rate = fields.Float(readonly=True)
    last_visit_date = fields.Date(readonly=True)
    latest_submitted_at = fields.Datetime(readonly=True)

    def init(self):
        self.env.cr.execute(
            f"""
            DROP VIEW IF EXISTS {self._table} CASCADE;
            CREATE OR REPLACE VIEW {self._table} AS
            SELECT
                row_number() OVER (ORDER BY visit.department_id) AS id,
                visit.department_id AS department_id,
                COUNT(visit.id) AS visit_count,
                COUNT(*) FILTER (WHERE visit.state = 'submitted') AS submitted_visit_count,
                COUNT(*) FILTER (WHERE visit.state = 'draft') AS draft_visit_count,
                COALESCE(AVG(visit.earned_total_score) FILTER (WHERE visit.state = 'submitted'), 0) AS avg_earned_score,
                COALESCE(AVG(visit.total_percentage) FILTER (WHERE visit.state = 'submitted'), 0) AS avg_percentage,
                COALESCE(MAX(visit.total_percentage) FILTER (WHERE visit.state = 'submitted'), 0) AS best_percentage,
                COALESCE(
                    (
                        COUNT(*) FILTER (WHERE visit.state = 'submitted')::numeric
                        / NULLIF(COUNT(visit.id), 0)::numeric
                    ) * 100,
                    0
                ) AS submission_rate,
                MAX(visit.visit_date) AS last_visit_date,
                MAX(visit.submitted_at) AS latest_submitted_at
            FROM ab_quality_assurance_visit visit
            GROUP BY visit.department_id
            """
        )
