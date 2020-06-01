# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, tools, _, SUPERUSER_ID
import json
import requests

import logging
_logger = logging.getLogger(__name__)


class FoodicsGetCustomer(models.Model):
    _name = "foodics.get.customer"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'image.mixin']
    _description = "Foodics Get Customer"

    def _call_get_customer(self):
        """ Called by cron job"""
        self.sudo().get_customer()


    def get_customer(self):
        '''
        Request url = "https://dash.foodics.com/api/v2/customers?page=1
        Method - GET
        headers = {'Authorization': 'Bearer ' + auth_token}
        Response - {
            "categories": "[{data}]"
        }
        '''
        foodics_history_obj = self.env['foodics.pos.history']
        customer_mapping_obj = self.env['foodics.customer.mapping']
        auth_token = self.env['foodics.configuration'].fetch_token()
        if auth_token:
            business_hid = self.env['foodics.get.business'].fetch_business()
            url = "https://dash.foodics.com/api/v2/customers?page=1"
            payload = {}
            headers = {'X-business': business_hid,
                       'Authorization': 'Bearer ' + auth_token}

            response = requests.request("GET", url, headers=headers, data=payload)

            if response.status_code == 200:
                get_data_in_dic = json.loads(response.text)
                customer_li = get_data_in_dic['customers']
                if customer_li:
                    for customer_dic in customer_li:
                        customer_mapping_id = customer_mapping_obj.search(
                                [('partner_foodics_id', '=', customer_dic['hid'])], limit=1)
                        if not customer_mapping_id:
                            foodics_history_obj.create({
                                'response': response.text,
                                'api_type': 'Customers',
                                'status_code': response.status_code,
                                'status': 'draft',
                            })
                            break


class FoodicsCUstomerProcess(models.Model):
    _name = "foodics.customer.process"

    def process_customer(self, history_obj, data):
        '''
        Improvement TODO
        {
          "customers": [
            {
              "name": "Tobin",
              "phone": "529098869",
              "email": null,
              "address": "",
              "notes": "",
              "blacklist": false,
              "created_at": "2019-05-29 12:12:26",
              "updated_at": "2019-05-29 12:12:26",
              "hid": "_72421585",
              "country": {
                "code": "AE",
                "hid": "_1527947d"
              }
            },
            {
              "name": "Marc",
              "phone": "529606073",
              "email": null,
              "address": "",
              "notes": "",
              "blacklist": false,
              "created_at": "2019-05-29 12:13:14",
              "updated_at": "2019-05-29 12:13:14",
              "hid": "_74915g4d",
              "country": {
                "code": "AE",
                "hid": "_1527947d"
              }
            }
          ]
        }
        '''
        history_obj.write({'status': 'inprocess'})
        partner_obj = self.env['res.partner']
        customer_mapping_obj = self.env['foodics.customer.mapping']
        get_data_in_dic = json.loads(data)
        customer_li = get_data_in_dic['customers']
        if customer_li:
            for customer_dic in customer_li:
                if 'name' in customer_dic:
                    partner_id = partner_obj.search(
                        [('name', '=', customer_dic['name']),
                         ('phone', '=', customer_dic['phone'])], limit=1)
                    if not partner_id:
                        country_id = self.env['res.country'].search(
                            [('code', '=', customer_dic['country']['code'])])
                        # Create Customer
                        try:
                            partner_id = partner_obj.create({
                                'name': customer_dic['name'],
                                'phone': customer_dic['phone'],
                                'email': customer_dic['email'],
                                'comment': customer_dic['notes'],
                                'country_id': country_id.id if country_id else False,
                                #'street': customer_dic['addresses'][0]['address'],
                            })
                            self._cr.commit()
                        except:
                            history_obj.write({'status': 'exceptions'})

                        # Create mapping record
                        try:
                            mapping_rec_id = customer_mapping_obj.create({
                                'partner_id': partner_id.id,
                                'partner_odoo_id': partner_id.id,
                                'partner_foodics_id': customer_dic['hid'],
                                'foodics_created_date': customer_dic['created_at'],
                                'foodics_update_date': customer_dic['updated_at'],
                                'blacklist': str(customer_dic['blacklist']),
                            })
                            history_obj.write({'status': 'done'})
                        except:
                            history_obj.write({'status': 'exceptions'})

                    else:
                        customer_mapping_id = customer_mapping_obj.search(
                            [('partner_id', '=', partner_id.id)], limit=1)
                        if not customer_mapping_id:
                            try:
                                mapping_rec_id = customer_mapping_obj.create({
                                    'partner_id': partner_id.id,
                                    'partner_odoo_id': partner_id.id,
                                    'partner_foodics_id': customer_dic['hid'],
                                    'foodics_created_date': customer_dic['created_at'],
                                    'foodics_update_date': customer_dic['updated_at'],
                                    'blacklist': str(customer_dic['blacklist']),
                                })
                            except:
                                history_obj.write({'status': 'exceptions'}) 
                        history_obj.write({'status': 'done'})
                else:
                    history_obj.write({'status': 'exceptions'})
        else:
            history_obj.write({'status': 'exceptions'})
