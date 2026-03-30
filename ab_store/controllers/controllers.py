# -*- coding: utf-8 -*-
# from odoo import http


# class AbStore(http.Controller):
#     @http.route('/ab_store/ab_store', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/ab_store/ab_store/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('ab_store.listing', {
#             'root': '/ab_store/ab_store',
#             'objects': http.request.env['ab_store.ab_store'].search([]),
#         })

#     @http.route('/ab_store/ab_store/objects/<model("ab_store.ab_store"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('ab_store.object', {
#             'object': obj
#         })
