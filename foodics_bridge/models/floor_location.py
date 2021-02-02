# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, tools, _, SUPERUSER_ID
import json
import requests

import logging
_logger = logging.getLogger(__name__)


class FoodicsGetFloor(models.Model):
    _name = "foodics.get.floor"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'image.mixin']
    _description = "Foodics Get Floor Location"

    def get_floor(self):
        '''
        Request url = "https://dash.foodics.com/api/v2/floor-locations"
        Method - GET
        headers = {'Authorization': 'Bearer ' + auth_token}
        Response - {
            "locations": "[{data}]"
        }
        '''
        foodics_history_obj = self.env['foodics.pos.history']
        auth_token = self.env['foodics.configuration'].fetch_token()
        business_hid = self.env['foodics.get.business'].fetch_business()
        url = "https://dash.foodics.com/api/v2/floor-locations"
        payload = {}
        headers = {'X-business': business_hid,
                   'Authorization': 'Bearer ' + auth_token}

        response = requests.request("GET", url, headers=headers, data=payload)

        if response.status_code == 200:
            foodics_history_obj.create({
                'response': response.text,
                'api_type': 'Floor-location',
                'status_code': response.status_code,
                'status': 'draft',
            })
        else:
            foodics_history_obj.create({
                'response': response.text,
                'api_type': 'Floor-location',
                'status_code': response.status_code,
                'status': 'exceptions',
            })


class FoodicsFloorProcess(models.Model):
    _name = "foodics.floor.process"
    
    def create_mapping_record(self, floor_id, location_dic):
        self.env['foodics.floor.location.mapping'].create({
            'floor_id': floor_id.id,
            'floor_odoo_id': floor_id.id,
            'floor_foodics_id': location_dic['hid'],
            'foodics_created_date': location_dic['created_at'],
            'foodics_update_date': location_dic['updated_at'],
        })

    def process_floor_location(self, history_obj, data):
        '''
        {
            "locations": [
               {
                    "name": {
                        "ar": "اسم الموقع",
                        "en": "LOCATIOIN_NAME"
                    },
                    "created_at": "2017-09-09 23:37:06",
                    "updated_at": "2017-09-09 23:37:06",
                    "hid": "_csdsdf4",
                    "tables": [
                       {
                            "name": "Table 1",
                            "created_at": "2017-10-09 23:37:27",
                            "updated_at": "2017-10-09 23:37:27",
                            "hid": "_76433d57"
                        }
                    ],
                    "branch": {
                        "hid": "_9676aa78",
                        "disabled_order_types": [
                            1
                        ]
                    }
                }
            ]
        }
        '''
        history_obj.write({'status': 'inprocess'})
        floor_obj = self.env['restaurant.floor']
        floor_mapping_obj = self.env['foodics.floor.location.mapping']
        get_data_in_dic = json.loads(data)
        location_li = get_data_in_dic['locations']
        if location_li:
            for location_dic in location_li:
                if 'name' in location_dic:
                    location_en_name = location_dic['name']['en']
                    floor_id = floor_obj.search([('name', '=', location_en_name)], limit=1)
                    # Floor create
                    if not floor_id:
                        floor_id = floor_obj.create({
                            'name': location_en_name,
                        })
                        # Create mapping record
                        self.create_mapping_record(floor_id, location_dic)
                        history_obj.write({'status': 'done'})
                    else:
                        floor_mapping_id = floor_mapping_obj.search(
                            [('floor_id', '=', floor_id.id)])
                        if not floor_mapping_id:
                            self.create_mapping_record(floor_id, location_dic)
                        history_obj.write({'status': 'done'})
                else:
                    history_obj.write({'status': 'exceptions'})
        else:
            history_obj.write({'status': 'exceptions'})
