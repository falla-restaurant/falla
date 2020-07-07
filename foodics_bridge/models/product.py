# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, tools, _, SUPERUSER_ID
import json
import requests

import logging
_logger = logging.getLogger(__name__)


class ProductTemplateInherit(models.Model):
    _inherit = "product.template"

    foodid_id = fields.Char(string='Hid')


class FoodicsGetProduct(models.Model):
    _name = "foodics.get.product"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'image.mixin']
    _description = "Foodics Get Product"

    def get_product(self):
        '''
        Request url = "https://dash.foodics.com/api/v2/products"
        Method - GET
        headers = {'Authorization': 'Bearer ' + auth_token}
        Response - {
            "products": "[{data}]"
        }
        '''
        foodics_history_obj = self.env['foodics.pos.history']
        auth_token = self.env['foodics.configuration'].fetch_token()
        business_hid = self.env['foodics.get.business'].fetch_business()
        url = "https://dash.foodics.com/api/v2/products"
        payload = {}
        headers = {'X-business': business_hid,
                   'Authorization': 'Bearer ' + auth_token}

        response = requests.request("GET", url, headers=headers, data=payload)

        if response.status_code == 200:
            foodics_history_obj.create({
                'response': response.text,
                'api_type': 'Products',
                'status_code': response.status_code,
                'status': 'draft',
            })
        else:
            foodics_history_obj.create({
                'response': response.text,
                'api_type': 'Products',
                'status_code': response.status_code,
                'status': 'exceptions',
            })


class FoodicsCategoryProduct(models.Model):
    _name = "foodics.product.process"

    def get_product_tax(self, product_dic, name):
        tax_id = False

        if name == "Delivery charges" or name == "Discount":
            configuration_obj = self.env[
                'foodics.configuration'].search([], limit=1)
            tax_id = configuration_obj.excluded_taxes_id
        else:
            configuration_obj = self.env[
                'foodics.configuration'].search([], limit=1)
            tax_id = configuration_obj.included_taxes_id

        if tax_id:
            return tax_id.id
        # Improvement TODO
        else:
            tax_id = False
            return tax_id
        
    def create_mapping_record(self, product_id, product_dic):
        product_mapping_obj = self.env['foodics.product.mapping']
        product_mapping_obj.create({
            'product_id': product_id.id,
            'product_odoo_id': product_id.id,
            'product_foodics_id': product_dic['hid'],
            'sku': product_dic['sku'],
            'foodics_created_date': product_dic['created_at'],
            'foodics_update_date': product_dic['updated_at'],
        })
        
    def check_mapping_record(self, product_id, product_dic, product_mapping_obj):
        product_mapping_res = product_mapping_obj.search(
            [('product_id', '=', product_id.id)])
        if not product_mapping_res:
            product_mapping_id = product_mapping_obj.search(
                [('product_foodics_id', '=', product_dic['hid'])])
            if product_mapping_id:
                product_mapping_id.write(
                    {'product_id': product_id.id})
            else:
                self.create_mapping_record(product_id, product_dic)

    def process_products(self, history_obj, data):
        '''
        {
          "products": [
            {
              "name": {
                "en": "MOCCHA LATTE",
                "ar": "MOCCHA LATTE"
              },
              "description": {
                "en": "null",
                "ar": "null"
              },
              "preparation_time_in_minutes": 8,
              "calories": null,
              "index": 0,
              "pricing_type": 1,
              "selling_type": 1,
              "is_active": true,
              "barcode": null,
              "sku": "FP0002",
              "taxable": true,
              "is_combo": false,
              "image_path": null,
              "created_at": "2019-05-20 11:35:31",
              "updated_at": "2019-05-20 11:35:31",
              "hid": "_722gaa49",
              "category": {
                "hid": "_792188d7"
              },
              "tags": [

              ],
              "modifiers": [
                {
                  "hid": "_722g9857",
                  "relationship_data": {
                    "index": 1,
                    "is_required": false,
                    "minimum_options": 0,
                    "maximum_options": 100,
                    "excluded_options": [

                    ]
                  }
                },
                {
                  "hid": "_74183917",
                  "relationship_data": {
                    "index": 1,
                    "is_required": false,
                    "minimum_options": 0,
                    "maximum_options": 100,
                    "excluded_options": [

                    ]
                  }
                }
              ],
              "sizes": [

              ],
              "timed_events": [

              ],
              "combo_items": [

              ]
            }
          ]
        }
        '''
        history_obj.write({'status': 'inprocess'})
        product_obj = self.env['product.template']
        product_mapping_obj = self.env['foodics.product.mapping']
        get_data_in_dic = json.loads(data)
        product_li = get_data_in_dic['products']
        if product_li:
            for product_dic in product_li:
                if 'name' in product_dic:
                    # Product create or select
                    product_en_name = product_dic['name']['en']
                    # Tax create or select
                    tax_id = False
                    if product_dic['taxable'] == True:
                        tax_id = self.get_product_tax(
                            product_dic, product_en_name)

                    product_id = False
                    product_mapping_id = product_mapping_obj.search(
                        [('product_foodics_id', '=', product_dic['hid']),
                         ('product_id', '!=', False)])
                    if product_mapping_id:
                        product_id = product_mapping_id[0].product_id
                    if not product_id:
                        description = ''
                        if product_dic['description']:
                            description = product_dic['description']['en']

                        barcode = product_dic['barcode']
                        category_id = False
                        if product_dic['category']:
                            category_id = self.env['foodics.category.mapping'].search([
                                ('category_foodics_id', '=', product_dic['category']['hid'])])

                        # Create Product
                        product_id = product_obj.create({
                            'name': product_en_name,
                            'description': description,
                            'barcode': barcode,
                            'available_in_pos': 1,
                            'foodid_id': product_dic['hid'],
                            'categ_id': category_id.category_id.id if category_id else 1,
                        })
                        if tax_id:
                            product_id.write({'taxes_id': [(6, 0, [tax_id])]})

                        # Create mapping record
                        self.create_mapping_record(product_id, product_dic)
                        history_obj.write({'status': 'done'})
                    else:
                        self.check_mapping_record(product_id, product_dic, product_mapping_obj)
                        history_obj.write({'status': 'done'})

                    # Create modifiers
                    # variant_obj = self.env['product.template.attribute.line']
                    # if product_dic['modifiers']:
                    #     for modifiers_data in product_dic['modifiers']:
                    #         if modifiers_data['relationship_data']:
                    #             modifier_mapping_id = self.env['foodics.modifier.mapping'].search(
                    #                 [('modifier_foodics_id', '=', modifiers_data['hid'])])
                    #             if modifier_mapping_id:
                    #                 excluded_options_li = []
                    #                 value_list = []
                    #                 for excluded_hid in modifiers_data['relationship_data']['excluded_options']:
                    #                     excluded_options_li.append(excluded_hid)

                    #                 for option_values in modifier_mapping_id.value_ids:
                    #                     if option_values.option_foodics_id not in excluded_options_li:
                    #                         value_id = self.env['product.attribute.value'].search(
                    #                             [('name', '=', option_values.name),
                    #                                 ('attribute_id', '=', modifier_mapping_id.product_id.id)], limit=1)
                    #                         value_list.append(value_id.id)
                    #                 for value_data in modifier_mapping_id.product_id.value_ids:
                    #                     if value_data.is_default:
                    #                         if value_data.id not in value_list:
                    #                             value_list.append(value_data.id)

                    #                 variant_id = variant_obj.search(
                    #                     [('attribute_id', '=', modifier_mapping_id.product_id.id),
                    #                         ('product_tmpl_id', '=', product_id.id)])

                    #                 if not variant_id:
                    #                     variant_obj.create({
                    #                         'attribute_id': modifier_mapping_id.product_id.id,
                    #                         'value_ids': [(6, 0, value_list)],
                    #                         'product_tmpl_id': product_id.id,
                    #                     })
                                        # self._cr.commit()
                else:
                    history_obj.write({'status': 'exceptions'})
        else:
            history_obj.write({'status': 'exceptions'})
