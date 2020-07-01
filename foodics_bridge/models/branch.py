# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, tools, _, SUPERUSER_ID
from odoo import exceptions, _
import json
import requests

import logging
_logger = logging.getLogger(__name__)


class FoodicsGetBranch(models.Model):
    _name = "foodics.get.branch"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'image.mixin']
    _description = "Foodics Get Branch"

    def _call_get_branch(self):
        """ Called by cron job"""
        self.sudo().get_branch()

    def get_branch(self):
        '''
        Request url = "https://dash.foodics.com/api/v2/branches"
        Method - GET
        headers = {'Authorization': 'Bearer ' + auth_token}
        Response - {
            "branches": "[{data}]"
        }
        '''
        foodics_history_obj = self.env['foodics.pos.history']
        auth_token = self.env['foodics.configuration'].fetch_token()
        business_hid = self.env['foodics.get.business'].fetch_business()
        url = "https://dash.foodics.com/api/v2/branches"
        payload = {}
        headers = {'X-business': business_hid,
                   'Authorization': 'Bearer ' + auth_token}

        response = requests.request("GET", url, headers=headers, data=payload)

        if response.status_code == 200:
            foodics_history_obj.create({
                'response': response.text,
                'api_type': 'Branches',
                'status_code': response.status_code,
                'status': 'draft',
            })
        else:
            foodics_history_obj.create({
                'response': response.text,
                'api_type': 'Branches',
                'status_code': response.status_code,
                'status': 'exceptions',
            })


class FoodicsBranchProcess(models.Model):
    _name = "foodics.branch.process"

    def process_branches(self, history_obj, data):
        '''
        {
            "branches": [
               {
                    "name": {
                        "en": "Main Branch",
                        "ar": "المكتب الرئيسي"
                    },
                    "reference": "B123",
                    "phone": "12345678",
                    "service_fees": 4,
                    "receipt_configs": {
                        "header": "Header",
                        "footer": "Footer"
                    },
                    "delivery_zones": [
                       {
                            "hid": "_a1671278"
                        }
                    ],
                    "taxes": [
                       {
                            "hid": "_716a2274"
                        }
                    ],
                    "city": {
                        "hid": "_d567ag7a"
                    },
                    "disabled_order_types": [
                        "3"
                    ],
                    "type": 1,
                    "latitude": "90.87687",
                    "longitude": "90.87687",
                    "open_from": "11",
                    "open_till": "2",
                    "accepts_online_orders": true,
                    "pickup_promising_time": 0,
                    "delivery_promising_time": 0,
                    "hid": "_6d7hs7s3",
                    "created_at": "2017-10-10 10:23:32",
                    "updated_at": "2018-08-16 09:38:38"
                }
            ]
        }
        '''
        history_obj.write({'status': 'inprocess'})
        warehouse_obj = self.env['stock.warehouse']
        pos_config_obj = self.env['pos.config']
        branch_mapping_obj = self.env['foodics.branch.mapping']
        get_data_in_dic = json.loads(data)
        branchs_li = get_data_in_dic['branches']
        if branchs_li:
            configuration_obj = self.env['foodics.configuration'].search([], limit=1)
            for branch_dic in branchs_li:
                if 'name' in branch_dic:
                    branch_en_name = branch_dic['name']['en']
                    warehouse_id = warehouse_obj.search(
                        [('name', '=', branch_en_name), ('code', '=', branch_dic['reference'])])
                    
                    # Warehouse create
                    if not warehouse_id:
                        if configuration_obj.warehouse_create == True:
                            try:
                                warehouse_id = warehouse_obj.create({
                                    'name': branch_en_name,
                                    'code': branch_dic['reference'],
                                })
                            except:
                                history_obj.write({'status': 'exceptions'})

                            # Create PoS Config
                            picking_type_id = self.env['stock.picking.type'].search([
                                    ('name', '=', 'PoS Orders'),
                                    ('warehouse_id', '=', warehouse_id.id)], limit=1)
                            try:
                                pos_config_id = pos_config_obj.create({
                                    'name': branch_en_name,
                                    'module_pos_restaurant': True,
                                    'picking_type_id': picking_type_id.id if picking_type_id else False,
                                })
                            except:
                                history_obj.write({'status': 'exceptions'})

                            # Create mapping record
                            mapping_rec_id = branch_mapping_obj.create({
                                'branch_id': warehouse_id.id,
                                'branch_name': branch_en_name,
                                'branch_odoo_id': warehouse_id.id,
                                'branch_foodics_id': branch_dic['hid'],
                                'foodics_created_date': branch_dic['created_at'],
                                'foodics_update_date': branch_dic['updated_at'],
                            })
                            history_obj.write({'status': 'done'})
                        else:
                            # Create mapping record
                            mapping_rec_id = branch_mapping_obj.create({
                                #'branch_id': ,
                                'branch_name': branch_en_name,
                                #'branch_odoo_id': warehouse_id.id,
                                'branch_foodics_id': branch_dic['hid'],
                                'foodics_created_date': branch_dic['created_at'],
                                'foodics_update_date': branch_dic['updated_at'],
                            })
                            history_obj.write({'status': 'done'})
                    else:
                        # Create PoS Config
                        picking_type_id = self.env['stock.picking.type'].search([
                                ('name', '=', 'PoS Orders'),
                                ('warehouse_id', '=', warehouse_id.id)], limit=1)
                        if picking_type_id:
                            pos_config_id = pos_config_obj.search([
                                    ('name', '=', branch_en_name),
                                    ('picking_type_id', '=', picking_type_id.id)], limit=1)
                            if not pos_config_id:
                                pos_config_id = pos_config_obj.create({
                                    'name': branch_en_name,
                                    'module_pos_restaurant': True,
                                    'picking_type_id': picking_type_id.id if picking_type_id else False,
                                })
                            
                        # Create mapping record
                        branch_mapping_id = branch_mapping_obj.search(
                            [('branch_id', '=', warehouse_id.id)])
                        if not branch_mapping_id:
                            mapping_rec_id = branch_mapping_obj.create({
                                'branch_id': warehouse_id.id,
                                'branch_name': branch_en_name,
                                'branch_odoo_id': warehouse_id.id,
                                'branch_foodics_id': branch_dic['hid'],
                                'foodics_created_date': branch_dic['created_at'],
                                'foodics_update_date': branch_dic['updated_at'],
                            })
                        else:
                            branch_mapping_id.write({'branch_name': branch_en_name})
                        history_obj.write({'status': 'done'})
                else:
                    history_obj.write({'status': 'exceptions'})
        else:
            history_obj.write({'status': 'exceptions'})
