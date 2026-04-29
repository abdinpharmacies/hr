from odoo import _, api, fields, models


class AbQualityAssuranceDepartmentDashboard(models.Model):
    _name = "ab_quality_assurance_department_dashboard"
    _description = "Quality Assurance Department Dashboard"
    _auto = False
    _rec_name = "department_id"

    department_id = fields.Many2one("ab_hr_department", string="Department", readonly=True)
    visit_count = fields.Integer(string="Total Visits", readonly=True)
    submitted_visit_count = fields.Integer(string="Submitted", readonly=True)
    draft_visit_count = fields.Integer(string="Draft", readonly=True)
    avg_earned_score = fields.Float(string="Avg Earned", readonly=True)
    avg_percentage = fields.Float(string="Average Score", readonly=True)
    best_percentage = fields.Float(string="Best Recorded", readonly=True)
    submission_rate = fields.Float(string="Submission Rate", readonly=True)
    last_visit_date = fields.Date(string="Latest Visit", readonly=True)
    latest_submitted_at = fields.Datetime(string="Latest Submission", readonly=True)
    ui_eyebrow = fields.Char(compute="_compute_ui_texts", readonly=True)
    ui_badge_label = fields.Char(compute="_compute_ui_texts", readonly=True)
    ui_average_score_label = fields.Char(compute="_compute_ui_texts", readonly=True)
    ui_best_recorded_label = fields.Char(compute="_compute_ui_texts", readonly=True)
    ui_submission_rate_label = fields.Char(compute="_compute_ui_texts", readonly=True)
    ui_total_visits_label = fields.Char(compute="_compute_ui_texts", readonly=True)
    ui_submitted_label = fields.Char(compute="_compute_ui_texts", readonly=True)
    ui_draft_label = fields.Char(compute="_compute_ui_texts", readonly=True)
    ui_avg_earned_label = fields.Char(compute="_compute_ui_texts", readonly=True)
    ui_latest_visit_label = fields.Char(compute="_compute_ui_texts", readonly=True)
    ui_latest_submission_label = fields.Char(compute="_compute_ui_texts", readonly=True)

    @api.depends("avg_percentage")
    @api.depends_context("lang")
    def _compute_ui_texts(self):
        for record in self:
            record.ui_eyebrow = _("Quality Assurance")
            if record.avg_percentage >= 85:
                record.ui_badge_label = _("Excellent")
            elif record.avg_percentage >= 70:
                record.ui_badge_label = _("Stable")
            else:
                record.ui_badge_label = _("Attention")
            record.ui_average_score_label = _("Average Score")
            record.ui_best_recorded_label = _("Best Recorded")
            record.ui_submission_rate_label = _("Submission Rate")
            record.ui_total_visits_label = _("Total Visits")
            record.ui_submitted_label = _("Submitted")
            record.ui_draft_label = _("Draft")
            record.ui_avg_earned_label = _("Avg Earned")
            record.ui_latest_visit_label = _("Latest Visit")
            record.ui_latest_submission_label = _("Latest Submission")

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
