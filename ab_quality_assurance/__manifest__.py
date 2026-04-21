{
    "name": "Quality Assurance",
    "version": "19.0.1.0.0",
    "license": "LGPL-3",
    "category": "Operations",
    "application": True,
    "depends": ["base", "web", "ab_hr"],
    "data": [
        "security/ir.model.access.csv",
        "security/security_groups.xml",
        "security/record_rules.xml",
        "data/ab_quality_assurance_sequence.xml",
        "views/ab_quality_assurance_section_views.xml",
        "views/ab_quality_assurance_standard_views.xml",
        "views/ab_quality_assurance_dashboard_views.xml",
        "views/ab_quality_assurance_visit_views.xml",
        "views/menus.xml",
        "report/ab_quality_assurance_visit_report.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "ab_quality_assurance/static/src/js/ab_quality_assurance_form_controller.js",
            "ab_quality_assurance/static/src/scss/ab_quality_assurance.scss",
        ],
    },
    "post_init_hook": "post_init_hook",
    "installable": True,
}
