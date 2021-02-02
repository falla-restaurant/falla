# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import itertools
from odoo import api, fields, models, tools, _, SUPERUSER_ID
from odoo.exceptions import ValidationError, RedirectWarning, UserError
from odoo.osv import expression

import logging
_logger = logging.getLogger(__name__)


class FoodicsProductMapping(models.Model):
    _name = "foodics.product.mapping"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'image.mixin']
    _description = "Foodics Product Mapping"
    _rec_name = "product_foodics_id"

    product_id = fields.Many2one('product.template', string='Product')
    product_odoo_id = fields.Integer('Product Odoo Id')
    product_foodics_id = fields.Char('Product Foodics Id')
    sku = fields.Char('Sku')
    foodics_created_date = fields.Datetime(
        'Foodics Created Date', help='Date of creation in Foodics.')
    foodics_update_date = fields.Datetime(
        'Foodics Update Date', help='Date of update in Foodics.')


class FoodicsModifierMapping(models.Model):
    _name = "foodics.modifier.mapping"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'image.mixin']
    _description = "Foodics Modifier Mapping"
    _rec_name = "modifier_foodics_id"

    product_id = fields.Many2one('product.attribute', string='Modifier')
    product_odoo_id = fields.Integer('Modifier Odoo Id')
    modifier_foodics_id = fields.Char('Modifier Foodics Id')
    sku = fields.Char('Sku')
    foodics_created_date = fields.Datetime(
        'Foodics Created Date', help='Date of creation in Foodics.')
    foodics_update_date = fields.Datetime(
        'Foodics Update Date', help='Date of update in Foodics.')
    value_ids = fields.One2many('modifier.value', 'modifier_id', 'Values')


class ModifierValue(models.Model):
    _name = "modifier.value"

    name = fields.Char(string='Name')
    option_foodics_id = fields.Char('Option Hid')
    modifier_id = fields.Many2one('foodics.modifier.mapping', string="Modifier Id")



class FoodicsCategoryMapping(models.Model):
    _name = "foodics.category.mapping"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'image.mixin']
    _description = "Foodics Category Mapping"
    _rec_name = "category_foodics_id"

    category_id = fields.Many2one('product.category', string='Category')
    category_odoo_id = fields.Integer('Category Odoo Id')
    category_foodics_id = fields.Char('Category Foodics Id')
    parent_category_foodics_id = fields.Char("Parent Foodics Id")
    foodics_created_date = fields.Datetime(
        'Foodics Created Date', help='Date of creation in Foodics.')
    foodics_update_date = fields.Datetime(
        'Foodics Update Date', help='Date of update in Foodics.')
    # POS Category fields
    pos_category_id = fields.Many2one('pos.category', string='PoS Category')
    pos_category_odoo_id = fields.Integer('PoS Category Id')


class FoodicsCustomerMapping(models.Model):
    _name = "foodics.customer.mapping"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'image.mixin']
    _description = "Foodics Customer Mapping"
    _rec_name = "partner_foodics_id"

    partner_id = fields.Many2one('res.partner', string='Customer')
    partner_odoo_id = fields.Integer('Customer Odoo Id')
    partner_foodics_id = fields.Char('Customer Foodics Id')
    foodics_created_date = fields.Datetime(
        'Created At', help='Date of creation in Foodics.')
    foodics_update_date = fields.Datetime(
        'Updated At', help='Date of update in Foodics.')
    # Extra fields
    blacklist = fields.Char('Blacklist')
    country_foodics_id = fields.Char('Country Foodics Id')
    latitude = fields.Char('Latitude')
    longitude = fields.Char('Longitude')
    w3w_address = fields.Char('w3w_address')
    address_hid = fields.Char('Address Foodics id')
    delivery_zone_hid = fields.Char('Delivery Zone hid')


class FoodicsBranchMapping(models.Model):
    _name = "foodics.branch.mapping"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'image.mixin']
    _description = "Foodics Branch Mapping"
    _rec_name = "branch_foodics_id"

    branch_id = fields.Many2one('stock.warehouse', string='Branch')
    branch_name = fields.Char('Branch name')
    branch_odoo_id = fields.Integer('Branch Odoo Id')
    branch_foodics_id = fields.Char('Branch Foodics Id')
    foodics_created_date = fields.Datetime(
        'Foodics Created Date', help='Date of creation in Foodics.')
    foodics_update_date = fields.Datetime(
        'Foodics Update Date', help='Date of update in Foodics.')


class FoodicsFloorLocationMapping(models.Model):
    _name = "foodics.floor.location.mapping"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'image.mixin']
    _description = "Foodics Floor Location Mapping"
    _rec_name = "floor_foodics_id"

    floor_id = fields.Many2one('restaurant.floor', string='Floor')
    floor_odoo_id = fields.Integer('Floor Odoo Id')
    floor_foodics_id = fields.Char('Floor Foodics Id')
    foodics_created_date = fields.Datetime(
        'Foodics Created Date', help='Date of creation in Foodics.')
    foodics_update_date = fields.Datetime(
        'Foodics Update Date', help='Date of update in Foodics.')


class FoodicsPaymentMethodMapping(models.Model):
    _name = "foodics.payment.method.mapping"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'image.mixin']
    _description = "Foodics Payment Method Mapping"
    _rec_name = "payment_foodics_id"

    method_name = fields.Char('Payment Method Name')
    payment_foodics_id = fields.Char('Payment Method Foodics Id')
    foodics_created_date = fields.Datetime(
        'Foodics Created Date', help='Date of creation in Foodics.')
    foodics_update_date = fields.Datetime(
        'Foodics Update Date', help='Date of update in Foodics.')
    method_type = fields.Char('Type')
    method_code = fields.Char('Code')
    auto_open_cash_drawer = fields.Boolean('Auto Open Cash Drawer')


class FoodicsUserMapping(models.Model):
    _name = "foodics.user.mapping"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'image.mixin']
    _description = "Foodics User Mapping"
    _rec_name = "user_foodics_id"

    user_id = fields.Many2one('res.users', string='Uer')
    user_odoo_id = fields.Integer('User Odoo Id')
    user_foodics_id = fields.Char('User Foodics Id')
    foodics_created_date = fields.Datetime(
        'Foodics Created Date', help='Date of creation in Foodics.')
    foodics_update_date = fields.Datetime(
        'Foodics Update Date', help='Date of update in Foodics.')
    foodics_user_type = fields.Char('Type')
    foodics_user_name = fields.Char('User Name')
    foodics_employee_number = fields.Char('Emp Number')


class FoodicsTillLogsMapping(models.Model):
    _name = "foodics.till.logs.mapping"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'image.mixin']
    _description = "Foodics Till Logs Mapping"
    _rec_name = "session_foodics_id"

    session_id = fields.Many2one('pos.session', string='POS Session')
    session_odoo_id = fields.Integer('Session Odoo Id')
    session_foodics_id = fields.Char('Session Foodics Id')
    foodics_opened_at = fields.Datetime(
        'Session Open At', help='Session Open At.')
    foodics_closed_at = fields.Datetime(
        'Session Close At', help='Session Close At.')


class FoodicsOrdersMapping(models.Model):
    _name = "foodics.orders.mapping"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'image.mixin']
    _description = "Foodics Orders Mapping"
    _rec_name = "order_foodics_id"

    order_id = fields.Many2one('pos.order', string='POS Order')
    order_odoo_id = fields.Integer('Order Odoo Id')
    order_foodics_id = fields.Char('Order Foodics Id')
    foodics_created_date = fields.Datetime(
        'Foodics Created Date', help='Date of creation in Foodics.')
    foodics_update_date = fields.Datetime(
        'Foodics Update Date', help='Date of update in Foodics.')


class BusinessHidMapping(models.Model):
    _name = "business.hid.mapping"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'image.mixin']
    _description = "Business Hid Mapping"
    _rec_name = "business_hid"

    business_hid = fields.Char('Bussinees Id')
