# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request


class AbHrJobPostWebsite(http.Controller):

    @http.route(['/jobs'], type='http', auth='public', website=True, sitemap=True)
    def job_list(self, **kw):
        posts = request.env['ab_hr_job_post'].sudo().search([
            ('website_published', '=', True),
        ], order="status asc, registration_start desc, sequence asc, id desc")

        return request.render('ab_hr_applicant.ab_hr_job_post_website_list', {
            'posts': posts
        })

    @http.route(['/jobs/apply?<int:post_id>'], type='http', auth='public', website=True, sitemap=False)
    def job_apply(self, post_id, **kw):
        post = request.env['ab_hr_job_post'].sudo().browse(post_id)
        apply_url = f"/jobs/apply_form?post_id={post.id}"
        return request.redirect(apply_url)
