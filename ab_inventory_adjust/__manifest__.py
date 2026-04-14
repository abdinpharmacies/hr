{
    'name': 'Abdin Adjustment Inventory Eplus',
    'version': '19.0.1.0.0',
    'license': 'LGPL-3',
    'depends': ['base', 'ab_product', 'ab_store', 'ab_eplus_connect', 'ab_eplus_replication', 'ab_hr'],
    'category': 'AbdinSupplyChain',
    'installable': True,
    'data': ["security/security_groups.xml",
             "security/record_rules.xml",
             "security/ir.model.access.csv",
             'views/menus.xml',
             'views/ab_inventory_adjust.xml',
             'views/ab_inventory_adjust_line.xml',
             'views/ab_inventory_adjust_product.xml',
             'views/ab_inventory_eplus.xml',
             ],
    'assets': {
        'web.assets_backend': [
            # 'ab_inventory_adjust/static/src/js/barcode_list_view.js',
            # 'ab_inventory_adjust/static/src/js/get_inventory_details.js',
            'ab_inventory_adjust/static/src/js/override_enter_key_abstract_field.js',
            'ab_inventory_adjust/static/src/js/helper_functions.js',
            'ab_inventory_adjust/static/src/js/odoo_barcode_one2many.js',
        ],
    },

}
