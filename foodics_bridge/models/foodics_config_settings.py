# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import requests
import json


class FoodicsConfigure(models.Model):
    _name = "foodics.configuration"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'image.mixin']
    _description = "Foodics Token"
    _rec_name = "end_point"

    name = fields.Char('Base URL', translate=True)
    end_point = fields.Char('API End-Point', translate=True)
    secret = fields.Char('Secret', translate=True)
    status_code = fields.Char('Status Code', translate=True)
    token = fields.Text('Token', translate=True)
    amount_adjust = fields.Boolean('Adjustment ?')
    warehouse_create = fields.Boolean('Auto Warehouse Create ?')
    delivery_product_id = fields.Many2one(
        'product.product', string="Delivery Product")
    adjustment_product_id = fields.Many2one(
        'product.product', string="Adjustment Product")
    discount_product_id = fields.Many2one(
        'product.product', string="Discount Product")
    included_taxes_id = fields.Many2one('account.tax', string='Inclusive Customer Taxes',
                                domain=[('type_tax_use', '=', 'sale'), ('price_include', '=', True)])
    excluded_taxes_id = fields.Many2one('account.tax', string='Exclusive Customer Taxes',
                                    domain=[('type_tax_use', '=', 'sale'), ('price_include', '=', False)])

    @api.constrains('name')
    def validate_name(self):
        count = 0
        rec = self.env['foodics.configuration'].search([])
        for obj in rec:
            count = count + 1
        if count <= 1:
            return True
        else:
            raise ValidationError(_("Only one record is allowed"))

    def get_token(self):
        '''
        Request URL - 'https://dash.foodics.com /api/v2/token'
        Method - POST
        Request Body - {"secret": "6BTURDW0D3L2MYSTRSQA"}
        Response - {
            "token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJhcHAiLCJhcHAiOjQ4NiwiYnVzIjpudWxsLCJjb21wIjpudWxsLCJzY3J0IjoiOUxVTDhGIn0.yY7G5_kVJ0mW22X4EaqpEJl-VouPAPqZaqUgjCU_2a0"
        }
        '''
        url = 'https://dash.foodics.com/api/v2/token'
        body = {"secret": self.secret}
        raw_response = requests.post(url, data=body)
        if raw_response.status_code == 200:
            response_in_dic = json.loads(raw_response.text)
            token = response_in_dic['token']
            self.write({'token': token,
                        'status_code': raw_response.status_code,
                        })
        else:
            self.write({'token': 'Exceptions',
                        'status_code': raw_response.status_code,
                        })

    def fetch_token(self):
        token_data = self.search(
            [('status_code', '=', '200')], limit=1)
        if token_data:
            return token_data.token
        else:
            return False


class FoodicsGetBusinesses(models.Model):
    _name = "foodics.get.business"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'image.mixin']
    _description = "Allowed Businesses"
    _rec_name = "end_point"

    name = fields.Char('Base URL', translate=True)
    end_point = fields.Char('API End-Point', translate=True)
    business_hid = fields.Char('Business Hid', translate=True)
    status_code = fields.Char('Status Code', translate=True)
    response = fields.Text('Response', translate=True)

    def fetch_business(self):
        business_data = self.env['business.hid.mapping'].search(
            [('id', '!=', False)], limit=1)
        if business_data:
            return business_data.business_hid
        else:
            return False

    def get_business_hid(self):
        '''
        Request URL - "https://dash.foodics.com/api/v2/businesses"
        Method - GET
        headers = {'Authorization': 'Bearer ' + auth_token}
        Response - {
            "businesses": "[{data}]"
        }
        '''
        bussiness_hid_obj = self.env['business.hid.mapping']
        auth_token = self.env['foodics.configuration'].fetch_token()
        url = "https://dash.foodics.com/api/v2/businesses"
        payload = {}
        headers = {'Authorization': 'Bearer ' + auth_token}

        response = requests.request("GET", url, headers=headers, data=payload)

        if response.status_code == 200:
            response_in_dic = json.loads(response.text)
            business_hid = response_in_dic['businesses'][0]['hid']
            self.write({'response': response.text,
                        'business_hid': business_hid,
                        'status_code': response.status_code,
                        })
            # create bussiness mapping
            branch_mapping_id = bussiness_hid_obj.search(
                [('business_hid', '=', business_hid)])
            if branch_mapping_id:
                branch_mapping_id.write({
                    'business_hid': business_hid,
                })
            else:
                branch_mapping_id.create({
                    'business_hid': business_hid,
                })

        else:
            self.write({'response': 'Exceptions',
                        'business_hid': False,
                        'status_code': response.status_code,
                        })
