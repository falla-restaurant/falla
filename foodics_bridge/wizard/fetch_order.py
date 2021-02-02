# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, tools, _, SUPERUSER_ID

class FetchOrderData(models.TransientModel):
    _name = 'fetch.order.data'

    warehouse_id = fields.Many2one(
        'stock.warehouse', "Branch", required=True)
    bussiness_date = fields.Date("Bussiness Date", required=True)

    def fetch_order_data(self):
        print("--------", self.warehouse_id, self.bussiness_date)
        self.env['foodics.get.order'].get_order(self.warehouse_id, self.bussiness_date)
