# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, tools, _, SUPERUSER_ID
from odoo.osv import expression
import json

import logging
_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = "res.partner"

    latitude = fields.Char('Latitude')
    longitude = fields.Char('Longitude')


class FoodicsPosHistory(models.Model):
    _name = "foodics.pos.history"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'image.mixin']
    _description = "Foodics POS History"
    _rec_name = "api_type"

    # url = fields.Char('URL', translate=True)
    fail_reason = fields.Text('Reason', translate=True)
    response = fields.Text('Response', translate=True)
    api_type = fields.Selection([
        ('Branches', 'Branches'),
        ('Categories', 'Categories'),
        ('Products', 'Products'),
        ('Modifiers', 'Modifiers'),
        ('Customers', 'Customers'),
        ('Floor-location', 'Floor-Location'),
        ('Orders', 'Orders'),
        ('Payment-methods', 'Payment-Methods'),
        ('Users', 'Users'),
    ], string='API Type')
    status_code = fields.Char('Status Code', translate=True)
    status = fields.Selection([
        ('draft', 'Draft'),
        ('inprocess', 'InProcess'),
        ('exceptions', 'Exceptions'),
        ('done', 'Done'),
    ], string='Status', default='draft')

    def _call_action_process(self):
        """ Called by cron job"""
        history_data = self.search([('status', '=', 'draft')], limit=4)
        _logger.info("History data being process through cron %s", history_data)
        for process_data in history_data:
            _logger.info("=== Runing process data === %s", process_data)
            process_data.sudo().action_process()

    def action_process(self):
        branch_obj = self.env['foodics.branch.process']
        category_obj = self.env['foodics.category.process']
        customer_obj = self.env['foodics.customer.process']
        product_obj = self.env['foodics.product.process']
        floor_obj = self.env['foodics.floor.process']
        payment_obj = self.env['foodics.payment_method.process']
        user_obj = self.env['foodics.user.process']
        order_obj = self.env['foodics.order.process']
        modifier_obj = self.env['foodics.modifiers.process']

        if self.api_type == 'Categories':
            category_obj.process_categories(self, self.response)
        elif self.api_type == 'Customers':
            customer_obj.process_customer(self, self.response)
        elif self.api_type == 'Branches':
            branch_obj.process_branches(self, self.response)
        elif self.api_type == 'Floor-location':
            floor_obj.process_floor_location(self, self.response)
        elif self.api_type == 'Products':
            product_obj.process_products(self, self.response)
        elif self.api_type == 'Payment-methods':
            payment_obj.process_payment_methods(self, self.response)
        elif self.api_type == 'Users':
            user_obj.process_users(self, self.response)
        elif self.api_type == 'Orders':
            order_obj.process_orders(self, self.response)
        elif self.api_type == 'Modifiers':
            modifier_obj.process_modifier(self, self.response)
