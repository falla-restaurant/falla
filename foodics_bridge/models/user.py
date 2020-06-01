# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, tools, _, SUPERUSER_ID
import json
import requests


class FoodicsGetUser(models.Model):
    _name = "foodics.get.user"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'image.mixin']
    _description = "Foodics Get User"

    def get_user(self):
        '''
        Request url = "https://dash.foodics.com/api/v2/users"
        Method - GET
        headers = {'Authorization': 'Bearer ' + auth_token}
        Response - {
            "users": "[{data}]"
        }
        '''
        foodics_history_obj = self.env['foodics.pos.history']
        auth_token = self.env['foodics.configuration'].fetch_token()
        business_hid = self.env['foodics.get.business'].fetch_business()
        url = self.branch_api_url
        payload = {}
        headers = {'X-business': business_hid,
                   'Authorization': 'Bearer ' + auth_token}

        response = requests.request("GET", url, headers=headers, data=payload)

        if response.status_code == 200:
            foodics_history_obj.create({
                'response': response.text,
                'api_type': 'Users',
                'status_code': response.status_code,
                'status': 'draft',
            })
        else:
            foodics_history_obj.create({
                'response': response.text,
                'api_type': 'Users',
                'status_code': response.status_code,
                'status': 'draft',
            })


class FoodicsUserProcess(models.Model):
    _name = "foodics.user.process"
    _description = "Process User"

    def process_users(self, history_obj, data):
        user_obj = self.env['res.users']
        user_mapping_obj = self.env['foodics.user.mapping']
        get_data_in_dic = json.loads(data)
        user_li = get_data_in_dic['users']
        count = 0
        for user_dic in user_li:
            count = count + 1
            if 'name' in user_dic:
                email = user_dic['email']
                user_id = user_obj.search([('login', '=', email)])
                if not user_id:
                    # Create User
                    user_id = user_obj.create({
                        'name': user_dic['name'],
                        'login': user_dic['email'],
                    })
                    # Update Partner record
                    partner_id = self.env['res.partner'].search(
                        [('id', '=', user_id.partner_id.id)])
                    if partner_id:
                        partner_id.write({
                            'mobile': user_dic['mobile'],
                            'email': user_dic['email'],
                        })
                    # Create mapping record
                    mapping_rec_id = user_mapping_obj.create({
                        'user_id': user_id.id,
                        'user_odoo_id': user_id.id,
                        'user_foodics_id': user_dic['hid'],
                        'foodics_created_date': user_dic['created_at'],
                        'foodics_update_date': user_dic['updated_at'],
                        'foodics_user_type': user_dic['type'],
                        'foodics_user_name': user_dic['username'],
                        'foodics_employee_number': user_dic['employee_number'],
                    })
                else:
                    user_mapping_id = user_mapping_obj.search(
                        [('user_id', '=', user_id.id)])
                    if not user_mapping_id:
                        mapping_rec_id = user_mapping_obj.create({
                            'user_id': user_id.id,
                            'user_odoo_id': user_id.id,
                            'user_foodics_id': user_dic['hid'],
                            'foodics_created_date': user_dic['created_at'],
                            'foodics_update_date': user_dic['updated_at'],
                            'foodics_user_type': user_dic['type'],
                            'foodics_user_name': user_dic['username'],
                            'foodics_employee_number': user_dic['employee_number'],
                        })
