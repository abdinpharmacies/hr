# -*- coding: utf-8 -*-
{
    "name": "Development Request Management",
    "version": "19.0.1.0.0",
    "summary": "Structured internal workflow for development requests",
    "description": """
Development Request Management
==============================

Centralize internal development requests from management to the development team.
Track reviews, approvals, assignments, deadlines, discussions, follow-ups, and
delivery outcomes with a structured Odoo 19 workflow.
""",
    "category": "Productivity",
    "author": "OpenAI",
    "license": "LGPL-3",
    "depends": ["base", "mail"],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "data/development_request_sequence.xml",
        "data/development_request_stage_data.xml",
        "data/development_request_team_data.xml",
        "data/development_request_category_data.xml",
        "data/ui_appearance_settings_data.xml",
        "data/development_request_cron.xml",
        "views/development_request_stage_views.xml",
        "views/development_request_team_views.xml",
        "views/development_request_category_views.xml",
        "views/development_request_views.xml",
        "views/development_request_followup_views.xml",
        "views/ui_appearance_settings_views.xml",
        "views/development_request_menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "dev_request_management/static/src/scss/development_request.scss",
            "dev_request_management/static/src/scss/theme_custom.scss",
            "dev_request_management/static/src/js/appearance_theme_service.js",
            "dev_request_management/static/src/js/appearance_theme_button.js",
            "dev_request_management/static/src/js/appearance_theme_dialog.js",
            "dev_request_management/static/src/xml/appearance_theme_templates.xml",
        ],
    },
    "application": True,
    "installable": True,
    "post_init_hook": "post_init_hook",
}
