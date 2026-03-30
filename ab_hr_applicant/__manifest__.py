# -*- coding: utf-8 -*-
{
    'name': "Abdin HR Applicant",
    'license': 'LGPL-3',
    'author': "Abdin Pharmacies",
    'category': 'Abdin',
    'version': '0.10',
    'depends': ['base', 'ab_hr', 'ab_cities', 'website', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'data/ab_hr_application_sequence.xml',
        'data/ab_hr_application_paperformat.xml',
        'views/ab_hr_application.xml',
        'views/ab_required_job.xml',
        'views/ab_hr_application_report.xml',
        'views/website_application_templates.xml',
        'views/ab_hr_job_post.xml',
        'views/website_job_post_templates.xml',
        'views/ab_hr_interview.xml',
        'views/ab_hr_interview_result_wizard.xml',

    ],
    'assets': {
        'web.assets_frontend': [
            'ab_hr_applicant/static/src/css/application_form.css',
            'ab_hr_applicant/static/src/js/application_form.js',
        ]
    },
}
