# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, tools, _, SUPERUSER_ID
import json
import requests

import logging
_logger = logging.getLogger(__name__)


class FoodicsGetCategory(models.Model):
    _name = "foodics.get.category"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'image.mixin']
    _description = "Foodics Get Category"

    def _call_get_category(self):
        """ Called by cron job"""
        self.sudo().get_category()

    def get_category(self):
        '''
        Request url = "https://dash.foodics.com/api/v2/categories"
        Method - GET
        headers = {'Authorization': 'Bearer ' + auth_token}
        Response - {
            "categories": "[{data}]"
        }
        '''
        foodics_history_obj = self.env['foodics.pos.history']
        auth_token = self.env['foodics.configuration'].fetch_token()
        business_hid = self.env['foodics.get.business'].fetch_business()
        url = "https://dash.foodics.com/api/v2/categories"
        payload = {}
        headers = {'X-business': business_hid,
                   'Authorization': 'Bearer ' + auth_token}

        response = requests.request("GET", url, headers=headers, data=payload)

        if response.status_code == 200:
            foodics_history_obj.create({
                'response': response.text,
                'api_type': 'Categories',
                'status_code': response.status_code,
                'status': 'draft',
            })
        else:
            foodics_history_obj.create({
                'response': response.text,
                'api_type': 'Categories',
                'status_code': response.status_code,
                'status': 'exceptions',
            })


class FoodicsCategoryProcess(models.Model):
    _name = "foodics.category.process"
    _description = "Process Category"

    def process_categories(self, history_obj, data):
        '''
        {
          "categories": [
            {
              "name": {
                "en": "Coffee",
                "ar": "Coffee"
              },
              "sku": "FC001",
              "index": 0,
              "image_path": "https:dash.foodics.comimgcategories_iconsother16.png",
              "created_at": "2019-05-20 10:53:36",
              "updated_at": "2019-05-26 11:58:17",
              "hid": "_792188d7",
              "timed_events": [

              ],
              "parent": null
            },
            {
              "name": {
                "en": "Cocktails",
                "ar": "Cocktails"
              },
              "sku": "FC002",
              "index": 1,
              "image_path": "https:dash.foodics.comimgcategories_iconsother02.png",
              "created_at": "2019-05-20 10:54:19",
              "updated_at": "2019-05-29 20:50:00",
              "hid": "_7aa81157",
              "timed_events": [

              ],
              "parent": null
                }
          ]
        }
        '''
        history_obj.write({'status': 'inprocess'})
        category_obj = self.env['product.category']
        pos_category_obj = self.env['pos.category']
        category_mapping_obj = self.env['foodics.category.mapping']
        get_data_in_dic = json.loads(data)
        category_li = get_data_in_dic['categories']
        if category_li:
            for category_dic in category_li:
                if 'name' in category_dic:
                    categ_en_name = category_dic['name']['en']

                    if category_dic['parent']:
                        parent_id = category_dic['parent']['hid']
                        parent_category_id = category_mapping_obj.search(
                            [('category_foodics_id', '=', str(parent_id))])
                    else:
                        parent_id = False
                        parent_category_id = False

                    # PoS Category create
                    pos_category_id = pos_category_obj.search(
                        [('name', '=', categ_en_name)])
                    if not pos_category_id:
                        pos_category_id = pos_category_obj.create({
                            'name': categ_en_name,
                            'parent_id': parent_category_id.pos_category_id.id if parent_category_id else False,
                        })
                    # Product Category create
                    category_id = category_obj.search(
                        [('name', '=', categ_en_name)], limit=1)
                    if not category_id:
                        # Create category
                        category_id = category_obj.create({
                            'name': categ_en_name,
                            'parent_id': parent_category_id.category_id.id if parent_category_id else False,
                        })
                        # Create mapping record
                        try:
                            mapping_rec_id = category_mapping_obj.create({
                                'category_id': category_id.id,
                                'category_odoo_id': category_id.id,
                                'pos_category_id': pos_category_id.id,
                                'pos_category_odoo_id': pos_category_id.id,
                                'category_foodics_id': category_dic['hid'],
                                'parent_category_foodics_id': parent_id,
                                'foodics_created_date': category_dic['created_at'],
                                'foodics_update_date': category_dic['updated_at'],
                            })
                            history_obj.write({'status': 'done'})
                        except:
                            history_obj.write({'status': 'exceptions'})
                    else:
                        category_mapping_id = category_mapping_obj.search(
                            [('category_id', '=', category_id.id)])
                        if not category_mapping_id:
                            try:
                                mapping_rec_id = category_mapping_obj.create({
                                    'category_id': category_id.id,
                                    'category_odoo_id': category_id.id,
                                    'category_foodics_id': category_dic['hid'],
                                    'parent_category_foodics_id': parent_id,
                                    'foodics_created_date': category_dic['created_at'],
                                    'foodics_update_date': category_dic['updated_at'],
                                })
                            except:
                                history_obj.write({'status': 'exceptions'})
                        history_obj.write({'status': 'done'})
                else:
                    history_obj.write({'status': 'exceptions'})
        else:
            history_obj.write({'status': 'exceptions'})
