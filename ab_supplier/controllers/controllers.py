# -*- coding: utf-8 -*-
# from odoo import http


# class Absupplier(http.Controller):
#     @http.route('/ab__supplier/ab__supplier', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/ab__supplier/ab__supplier/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('ab__supplier.listing', {
#             'root': '/ab__supplier/ab__supplier',
#             'objects': http.request.env['ab__supplier.ab__supplier'].search([]),
#         })

#     @http.route('/ab__supplier/ab__supplier/objects/<model("ab__supplier.ab__supplier"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('ab__supplier.object', {
#             'object': obj
#         })
