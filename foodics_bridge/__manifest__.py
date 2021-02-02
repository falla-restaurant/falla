# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Foodics Odoo Bridge',
    'version': '1.1',
    'category': 'Generic Module',
    'author': 'Prolitus Technology Pvt Ltd',

    'depends': ['base', 'mail', 'point_of_sale', 'pos_restaurant', 'mrp', 'product', 'account'],

    'description': """
        This Module Integrate Foodics with Odoo.
    """,
    'data': [
        'security/ir.model.access.csv',
        'data/foodic_pos_data.xml',
        'wizard/fetch_order_view.xml',

        'views/foodics_views.xml',
        'views/foodics_history_view.xml',
        'views/mapping_view.xml',
        'views/api_configuration_view.xml',
    ],
    'demo': [],
    'installable': True,
    'auto_install': False,
}
