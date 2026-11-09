# -*- coding: utf-8 -*-
# from odoo import http


# class abdin_eplus(http.Controller):
#     @http.route('/abdin_eplus/abdin_eplus/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/abdin_eplus/abdin_eplus/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('abdin_eplus.listing', {
#             'root': '/abdin_eplus/abdin_eplus',
#             'objects': http.request.env['abdin_eplus.abdin_eplus'].search([]),
#         })

#     @http.route('/abdin_eplus/abdin_eplus/objects/<model("abdin_eplus.abdin_eplus"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('abdin_eplus.object', {
#             'object': obj
#         })
