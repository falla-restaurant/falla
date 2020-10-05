from odoo import api, fields, models, tools, _, SUPERUSER_ID
import json
import requests

import logging
_logger = logging.getLogger(__name__)


class FoodicsGetModifiers(models.Model):
    _name = "foodics.get.modifiers"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'image.mixin']
    _description = "Foodics Get Modifiers"

    def get_modifiers(self):
        '''
        Request url = "https://dash.foodics.com/api/v2/modifiers"
        Method - GET
        headers = {'Authorization': 'Bearer ' + auth_token}
        Response - {
            "modifiers": "[{data}]"
        }
        '''
        foodics_history_obj = self.env['foodics.pos.history']
        auth_token = self.env['foodics.configuration'].fetch_token()
        business_hid = self.env['foodics.get.business'].fetch_business()
        url = "https://dash.foodics.com/api/v2/modifiers"
        payload = {}
        headers = {'X-business': business_hid,
                   'Authorization': 'Bearer ' + auth_token}

        response = requests.request("GET", url, headers=headers, data=payload)

        if response.status_code == 200:
            foodics_history_obj.create({
                'response': response.text,
                'api_type': 'Modifiers',
                'status_code': response.status_code,
                'status': 'draft',
            })
        else:
            foodics_history_obj.create({
                'response': response.text,
                'api_type': 'Modifiers',
                'status_code': response.status_code,
                'status': 'exceptions',
            })


class FoodicsModifiersProduct(models.Model):
    _name = "foodics.modifiers.process"
    
    def create_mapping_record(self, attribute_id, attribute_dic, value_li):
        self.env['foodics.modifier.mapping'].create({
            'product_id': attribute_id.id,
            'product_odoo_id': attribute_id.id,
            'modifier_foodics_id': attribute_dic['hid'],
            'sku': attribute_dic['sku'],
            'value_ids': value_li,
            'foodics_created_date': attribute_dic['created_at'],
            'foodics_update_date': attribute_dic['updated_at'],
        })

    def process_modifier(self, history_obj, data):
        '''
        {
            "modifiers": [
               {
                    "name": {
                        "ar": "MODIFIER_NAME",
                        "en": "MODIFIER_NAME"
                    },
                    "is_multiple": true,
                    "created_at": "2018-05-09 09:04:17",
                    "updated_at": "2018-05-09 09:04:17",
                    "BARCODE": "MODIFIER_BARCODE",
                    "sku": "MODIFIER_SKU",
                    "hid": "_567a437a",
                    "options": [
                       {
                            "name": {
                                "ar": "OPTION_NAME",
                                "en": "OPTION_NAME"
                            },
                            "sku": "MOSKU",
                            "price": 25,
                            "index": 0,
                            "created_at": "2018-05-09 09:04:17",
                            "updated_at": "2018-05-09 09:04:17",
                            "cost": 10,
                            "calories": 123,
                            "has_fixed_cost": true,
                            "taxable": true,
                            "hid": "_96764317",
                            "costingType": "fixed",
                            "ingredients": [],
                            "special_branch_prices": [
                               {
                                    "branch_hid": "_49676a78",
                                    "price": 12
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        '''
        history_obj.write({'status': 'inprocess'})
        attribute_obj = self.env['product.attribute']
        attribute_value_obj = self.env['product.attribute.value']
        attribute_mapping_obj = self.env['foodics.modifier.mapping']
        get_data_in_dic = json.loads(data)
        attribute_li = get_data_in_dic['modifiers']
        if attribute_li:
            for attribute_dic in attribute_li:
                if 'name' in attribute_dic:
                    # Attribute create or select
                    attribute_en_name = attribute_dic['name']['en']
                    _logger.info("attribute_en_name %s", attribute_en_name)
                   
                    attribute_id = attribute_obj.search(
                        [('name', '=', attribute_en_name)])
                    
                    _logger.info("search attributet %s", attribute_id)
                    if not attribute_id:
                        attribute_id = attribute_obj.create({
                            'name': attribute_en_name,
                            'create_variant': 'always',
                        })
                        _logger.info("create attribute %s", attribute_id)
                        value_li = []
                        for attribute_value in attribute_dic['options']:
                            value_en_name = attribute_value['name']['en']
                            value_id = attribute_value_obj.search([
                                ('name', '=', value_en_name),
                                ('attribute_id', '=', attribute_id.id)])
                            if not value_id:
                                attribute_value_obj.create({
                                    'name': value_en_name,
                                    'attribute_id': attribute_id.id,
                                })
                                value_li.append((0, 0, {
                                    'name': value_en_name,
                                    'option_foodics_id': attribute_value['hid'],
                                }))

                        # Create mapping record
                        self.create_mapping_record(attribute_id, attribute_dic, value_li)
                        history_obj.write({'status': 'done'})
                        self._cr.commit()
                    else:
                        product_mapping_id = attribute_mapping_obj.search(
                            [('product_id', '=', attribute_id.id)])
                        if not product_mapping_id:
                            value_li = []
                            for attribute_value in attribute_dic['options']:
                                value_en_name = attribute_value['name']['en']
                                value_li.append((0, 0, {
                                    'name': value_en_name,
                                    'option_foodics_id': attribute_value['hid'],
                                }))
                            self.create_mapping_record(attribute_id, attribute_dic, value_li)
                        history_obj.write({'status': 'done'})

                else:
                    history_obj.write({'status': 'exceptions'})
        else:
            history_obj.write({'status': 'exceptions'})
            
            