# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, tools, _, SUPERUSER_ID
from odoo.osv import expression


class ApiConfiguration(models.Model):
    _name = "api.configuration"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'image.mixin']
    _description = "API COnfiguration"

    def import_branch(self):
        self.env['foodics.get.branch'].get_branch()

    def import_category(self):
        self.env['foodics.get.category'].get_category()

    def import_customer(self):
        self.env['foodics.get.customer'].get_customer()

    def import_product(self):
        self.env['foodics.get.product'].get_product()

    def import_modifiers(self):
        self.env['foodics.get.modifiers'].get_modifiers()

    def import_floor_location(self):
        self.env['foodics.get.floor'].get_floor()

    def import_payment_method(self):
        self.env['foodics.get.payment_method'].get_payment_method()

    # def import_user(self):
    #     self.env['foodics.get.user'].get_user()

    def import_business_hid(self):
        self.env['foodics.get.business'].get_business_hid()
