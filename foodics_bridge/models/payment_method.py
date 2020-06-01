# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, tools, _, SUPERUSER_ID
import json
import requests

import logging
_logger = logging.getLogger(__name__)


class FoodicsGetPaymentMethod(models.Model):
    _name = "foodics.get.payment_method"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'image.mixin']
    _description = "Foodics Get Payment Method"

    def get_payment_method(self):
        '''
        Request url = "https://dash.foodics.com/api/v2/payment-methods"
        Method - GET
        headers = {'Authorization': 'Bearer ' + auth_token}
        Response - {
            "payment_methods": "[{data}]"
        }
        '''
        foodics_history_obj = self.env['foodics.pos.history']
        auth_token = self.env['foodics.configuration'].fetch_token()
        business_hid = self.env['foodics.get.business'].fetch_business()
        url = "https://dash.foodics.com/api/v2/payment-methods"
        payload = {}
        headers = {'X-business': business_hid,
                   'Authorization': 'Bearer ' + auth_token}

        response = requests.request("GET", url, headers=headers, data=payload)

        if response.status_code == 200:
            foodics_history_obj.create({
                'response': response.text,
                'api_type': 'Payment-methods',
                'status_code': response.status_code,
                'status': 'draft',
            })
        else:
            foodics_history_obj.create({
                'response': response.text,
                'api_type': 'Payment-methods',
                'status_code': response.status_code,
                'status': 'exceptions',
            })


class FoodicsPaymentMethodProcess(models.Model):
    _name = "foodics.payment_method.process"
    _description = "Process Get Payment Method"

    def process_payment_methods(self, history_obj, data):
        '''
        {
            "payment_methods": [
               {
                    "name": "METHOD_NAME",
                    "type": 1,
                    "is_active": true,
                    "created_at": "2018-05-08 11:24:01",
                    "updated_at": "2018-05-08 11:24:01",
                    "auto_open_cash_drawer": true,
                    "code": 123,
                    "hid": "_da7g4673"
                }
            ]
        }
        '''
        history_obj.write({'status': 'inprocess'})
        pos_payment_obj = self.env['pos.payment.method']
        payment_mapping_obj = self.env['foodics.payment.method.mapping']
        get_data_in_dic = json.loads(data)
        payment_li = get_data_in_dic['payment_methods']
        if payment_li:
            for payment_dic in payment_li:
                if 'name' in payment_dic:
                    method_en_name = payment_dic['name']
                    payment_id = pos_payment_obj.search(
                        [('name', '=', method_en_name)])
                    if not payment_id:

                        # companies = self.env['res.company'].search([])
                        # print("========81==================", companies)
                        # for company in companies:
                        #     print("========88==============", company)
                        #     if company.chart_template_id:
                        #         print("========90==============", company.chart_template_id)

                                # cash_journal = self.env['account.journal'].search([('company_id', '=', self.env.company.id),
                                # pos_receivable_account = company.account_default_pos_receivable_account_id
                                #                                                    ('type', '=', 'cash')], limit=1)
                                # print("=====86========", cash_journal)

                        # Create Payment Method
                        try:
                            payment_id = pos_payment_obj.create({
                                'name': method_en_name,
                            })
                        except:
                            history_obj.write({'status': 'exceptions'})



                        #qwertyuio
                        # Create mapping record
                        try:
                            mapping_rec_id = payment_mapping_obj.create({
                                'payment_id': payment_id.id,
                                'payment_odoo_id': payment_id.id,
                                'payment_foodics_id': payment_dic['hid'],
                                'foodics_created_date': payment_dic['created_at'],
                                'foodics_update_date': payment_dic['updated_at'],
                                'method_type': payment_dic['type'],
                                'method_code': payment_dic['code'],
                                'auto_open_cash_drawer': payment_dic['auto_open_cash_drawer'],
                            })
                        except:
                            history_obj.write({'status': 'exceptions'})
                    else:
                        payment_mapping_id = payment_mapping_obj.search(
                            [('payment_id', '=', payment_id.id)])
                        if not payment_mapping_id:
                            try:
                                mapping_rec_id = payment_mapping_obj.create({
                                    'payment_id': payment_id.id,
                                    'payment_odoo_id': payment_id.id,
                                    'payment_foodics_id': payment_dic['hid'],
                                    'foodics_created_date': payment_dic['created_at'],
                                    'foodics_update_date': payment_dic['updated_at'],
                                    'method_type': payment_dic['type'],
                                    'method_code': payment_dic['code'],
                                    'auto_open_cash_drawer': payment_dic['auto_open_cash_drawer'],
                                })
                            except:
                                history_obj.write({'status': 'exceptions'})
                        history_obj.write({'status': 'done'})
                else:
                    history_obj.write({'status': 'exceptions'})
        else:
            history_obj.write({'status': 'exceptions'})