# -*- coding: utf-8 -*-
# from odoo import http


# class AbCities(http.Controller):
#     @http.route('/ab_cities/ab_cities', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/ab_cities/ab_cities/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('ab_cities.listing', {
#             'root': '/ab_cities/ab_cities',
#             'objects': http.request.env['ab_cities.ab_cities'].search([]),
#         })

#     @http.route('/ab_cities/ab_cities/objects/<model("ab_cities.ab_cities"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('ab_cities.object', {
#             'object': obj
#         })
