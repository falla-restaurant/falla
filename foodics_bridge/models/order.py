# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models, tools, _, SUPERUSER_ID
from odoo.exceptions import UserError, ValidationError
import json
import requests
from datetime import date
import datetime

import logging
_logger = logging.getLogger(__name__)


class PosOrderInherit(models.Model):
    _inherit = "pos.order"

    foodic_name = fields.Char(string='Foodic Ref', required=True,
                              readonly=True, copy=False, default='/')


class PosOrderLineInherit(models.Model):
    _inherit = "pos.order.line"

    addons = fields.Char(string='Add-ons')


class ProductAttributeInherit(models.Model):
    _inherit = "product.attribute"

    @api.constrains('value_ids')  # wizard is the one2many field
    def _check_grade_choisi(self):
        count = 0
        for record in self.value_ids:
            if record.is_default == True:
                count = count+1
            if count > 1:
                raise ValidationError("You can select only one default attribute value")
        return True


class AttributeValueInherit(models.Model):
    _inherit = "product.attribute.value"

    is_default = fields.Boolean(string='Is Default ?')


class FoodicsGetOrder(models.Model):
    _name = "foodics.get.order"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'image.mixin']
    _description = "Foodics Get Order"

    def _call_get_order(self):
        """ Called by cron job"""
        filter_date = date.today()
        warehouses = self.env['stock.warehouse'].search([])
        for warehouse_id in warehouses:
            self.sudo().get_order(warehouse_id, filter_date)

    def get_order(self, warehouse_id, filter_date):
        '''
        Request url = "https://dash.foodics.com/api/v2/orders?filters%5Bbusiness_date%5D=2020-03-30&filters%5Bbranch_hid%5D=_27864a87
        Method - GET
        payload = {}
        headers = {
          'X-business': '_a7g369a7',
          'Authorization': 'Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJhcHAiLCJhcHAiOjQ4NiwiYnVzIjpudWxsLCJjb21wIjpudWxsLCJzY3J0IjoiOUxVTDhGIn0.yY7G5_kVJ0mW22X4EaqpEJl-VouPAPqZaqUgjCU_2a0',
          'Cookie': '__cfduid=dde06d47d003f8af9dc5f4730bf79f6301584940616'
        }
        Response - {
            "orders": "[{data}]"
        }
        '''
        foodics_history_obj = self.env['foodics.pos.history']
        order_mapping_obj = self.env['foodics.orders.mapping']
        auth_token = self.env['foodics.configuration'].fetch_token()
        if auth_token:
            business_hid = self.env['foodics.get.business'].fetch_business()

            url = "https://dash.foodics.com/api/v2/orders"
            branch_hid = self.env['foodics.branch.mapping'].search([
                ('branch_id', '=', warehouse_id.id)])

            url = url + "?filters%5Bbusiness_date%5D={}&filters%5Bbranch_hid%5D={}&filters%5Bstatus%5D=4".format(
                filter_date, branch_hid.branch_foodics_id)
            payload = {}
            headers = {'X-business': business_hid,
                       'Authorization': 'Bearer ' + auth_token}

            response = requests.request("GET", url, headers=headers, data=payload)

            if response.status_code == 200:
                get_data_in_dic = json.loads(response.text)
                order_li = get_data_in_dic['orders']
                if order_li:
                    for order_dic in order_li:
                        order_mapping_id = order_mapping_obj.search(
                                [('order_foodics_id', '=', order_dic['hid'])])
                        if not order_mapping_id:
                            foodics_history_obj.create({
                                'response': response.text,
                                'api_type': 'Orders',
                                'status_code': response.status_code,
                                'status': 'draft',
                            })
                            break


class FoodicsOrderProcess(models.Model):
    _name = "foodics.order.process"
    _description = "Process Order"

    def _call_process_pos_sessions(self):
        """ Called by cron job"""
        pos_session_ids = self.env['pos.session'].search(
            [('state', 'in', ('opened', 'closing_control'))])
        for session_id in pos_session_ids:
            dt = datetime.datetime.strptime(
                str(session_id.start_at), '%Y-%m-%d %H:%M:%S')
            if dt.date() < date.today():
                try:
                    session_id.action_pos_session_closing_control()
                except:
                    pass

    def get_pos_customer(self, hid, partner_name, customer_dic):
        customer_mapping_obj = self.env['foodics.customer.mapping']
        partner_obj = self.env['res.partner']

        partner_mapping_id = customer_mapping_obj.search([
            ('partner_foodics_id', '=', hid),
            ('partner_id.name', '=', partner_name)])

        if not partner_mapping_id:
            partner_id = partner_obj.create({
                'name': customer_dic['name'],
                'phone': customer_dic['phone'],
                'email': customer_dic['email'],
                'comment': customer_dic['notes'],
                'street': customer_dic['address'],
                #'country_id': country_id.id if country_id else False, # TODO
            })
            mapping_rec_id = customer_mapping_obj.create({
                'partner_id': partner_id.id,
                'partner_odoo_id': partner_id.id,
                'partner_foodics_id': customer_dic['hid'],
                'foodics_created_date': customer_dic['created_at'],
                'foodics_update_date': customer_dic['updated_at'],
                'blacklist': str(customer_dic['blacklist']),
            })
            return partner_id
        else:
            partner_id = partner_mapping_id.partner_id
            return partner_id

    def get_pos_session(self, pos_config_id, business_date):
        # session date should be business date
        _logger.info("Called get_pos_session")
        session_obj = self.env['pos.session']
        session_id = session_obj.search([
            ('config_id', '=', pos_config_id),
            ('state', 'in', ('new_session', 'opened'))], limit=1)
        _logger.info("get_pos_session -> session_id %s", session_id)
        if session_id:
            dt = datetime.datetime.strptime(
                str(session_id.start_at), '%Y-%m-%d %H:%M:%S')

            if str(dt.date()) == str(business_date):
                return session_id
            else:
                pos_orders = self.env['pos.order'].search([('session_id', '=', session_id.id)])
                for order_id in pos_orders:
                    if order_id.state != 'paid':
                        if round(order_id.amount_total, 2) == round(order_id.amount_paid, 2):
                            order_id.action_pos_order_paid()
                            #self._cr.commit()
                        else:
                            if order_id.amount_total != order_id.amount_paid:
                                adjustment_amount = order_id.amount_total - order_id.amount_paid
                                if adjustment_amount < 1 and adjustment_amount > -1:
                                    configuration_obj = self.env[
                                        'foodics.configuration'].search([], limit=1)
                                    adjustment_product_id = configuration_obj.adjustment_product_id
                                    if adjustment_product_id:
                                        new_line = order_id.lines.create({
                                            'order_id': order_id.id,
                                            'product_id': adjustment_product_id.id,
                                            'qty': 1,
                                            'price_unit': float(adjustment_amount) * -1,
                                            'price_subtotal': float(adjustment_amount) * -1,
                                            'price_subtotal_incl': float(adjustment_amount) * -1,
                                        })
                                        order_id._onchange_amount_all()
                                        order_id.action_pos_order_paid()

                _logger.info("==session status== %s", session_id.state)
                session_id.action_pos_session_closing_control()
                _logger.info("==session status after close call== %s", session_id.state)

                session_id = session_obj.create({
                    'user_id': self.env.uid,
                    'config_id': pos_config_id,
                    'start_at': str(business_date),
                })
                return session_id
        else:
            # check if any session open for this user and conf - close if any
            open_session_res = session_obj.search([('user_id', '=', self.env.uid),
                                                  ('config_id', '=', pos_config_id),
                                                  ('state', 'in', ['opened'])])
            _logger.info("== open_session_res == %s", open_session_res)
            for open_session_id in open_session_res:
                pos_orders = self.env['pos.order'].search([('session_id', '=', open_session_id.id)])
                for order_id in pos_orders:
                    if order_id.state != 'paid':
                        if round(order_id.amount_total, 2) == round(order_id.amount_paid, 2):
                            order_id.action_pos_order_paid()
                            self._cr.commit()
                        else:
                            if order_id.amount_total != order_id.amount_paid:
                                adjustment_amount = order_id.amount_total - order_id.amount_paid
                                if adjustment_amount < 1 and adjustment_amount > -1:
                                    configuration_obj = self.env[
                                        'foodics.configuration'].search([], limit=1)
                                    adjustment_product_id = configuration_obj.adjustment_product_id
                                    if adjustment_product_id:
                                        new_line = order_id.lines.create({
                                            'order_id': order_id.id,
                                            'product_id': adjustment_product_id.id,
                                            'qty': 1,
                                            'price_unit': float(adjustment_amount) * -1,
                                            'price_subtotal': float(adjustment_amount) * -1,
                                            'price_subtotal_incl': float(adjustment_amount) * -1,
                                        })
                                        order_id._onchange_amount_all()
                                        order_id.action_pos_order_paid()
                                        self._cr.commit()

                _logger.info("==session status== %s", open_session_id.state)
                open_session_id.action_pos_session_closing_control()
                _logger.info("==session status after close call== %s", open_session_id.state)


            session_id = session_obj.create({
                'user_id': self.env.uid,
                'config_id': pos_config_id,
                'start_at': business_date,
            })
            return session_id

    def get_order_line(self, order_dic):
        order_line_list = []
        # Create order Line
        for line_data in order_dic['products']:
            if not line_data['void_reason']:
                pro_map_id = self.env['foodics.product.mapping'].search([
                    ('product_foodics_id', '=', line_data['product_hid'])])
                if pro_map_id:
                    if not line_data['options']:
                        if not pro_map_id.product_id.attribute_line_ids:
                            product_pro_id  = self.env['product.product'].search(
                                                [('product_tmpl_id', '=', pro_map_id.product_id.id)], limit=1)
                            order_line_list.append((0, 0, {
                                'product_id': product_pro_id.id,
                                'qty': line_data['quantity'],
                                'price_unit': line_data['displayable_original_price'],
                                'price_subtotal': line_data['final_price'],
                                'price_subtotal_incl': line_data['displayable_final_price'],
                            }))
                        else:
                            product_pro_ids = self.env['product.product'].search(
                                                [('product_tmpl_id', '=', pro_map_id.product_id.id)])
                            keys = []
                            default_product = 0
                            for product_pro_id in product_pro_ids:
                                if keys and False not in keys:
                                    default_product = default_pro_variant_id.id
                                    break
                                keys.clear()
                                for attribute in product_pro_id.product_template_attribute_value_ids:
                                    default_pro_variant_id = product_pro_id
                                    keys.append(attribute.product_attribute_value_id.is_default)
                            if default_product > 0:
                                order_line_list.append((0, 0, {
                                    'product_id': default_product,
                                    'qty': line_data['quantity'],
                                    'price_unit': line_data['displayable_original_price'],
                                    'price_subtotal': line_data['final_price'],
                                    'price_subtotal_incl': line_data['displayable_final_price'],
                                }))
                            else:
                                # This case Need to be dicuss
                                order_line_list.append((0, 0, {
                                    'product_id': product_pro_ids[0].id,
                                    'qty': line_data['quantity'],
                                    'price_unit': line_data['displayable_original_price'],
                                    'price_subtotal': line_data['final_price'],
                                    'price_subtotal_incl': line_data['displayable_final_price'],
                                }))
                    # if we have modifier in options
                    else:
                        item_ids = []
                        modifier_ids = []
                        addon_total = 0.0
                        for oprtion_data in line_data['options']:

                            if oprtion_data['relationship_data']:
                                addon_qty = oprtion_data['relationship_data']['quantity']
                                addon_amount = round(oprtion_data['relationship_data']['original_price'], 3) * addon_qty
                                addon_total = addon_total + float(addon_amount)

                            modifier_option_id = self.env['modifier.value'].search(
                                            [('option_foodics_id', '=', oprtion_data['hid'])])
                            if modifier_option_id:
                                modifier_ids.append(modifier_option_id.modifier_id.product_id.id)
                                for items in modifier_option_id.modifier_id.product_id.value_ids:
                                    if items.name == modifier_option_id.name:
                                        item_ids.append(items.id)

                        if addon_total > 0:
                            addon_total_incl = (addon_total/10)/2 + addon_total
                        else:
                            addon_total_incl = 0

                        if pro_map_id.product_id.attribute_line_ids:
                            for tmp_attribute_line_id in pro_map_id.product_id.attribute_line_ids:
                                if tmp_attribute_line_id.attribute_id.id not in modifier_ids:
                                    value_id = self.env['product.attribute.value'].search(
                                                        [('is_default', '=', True),
                                                         ('attribute_id', '=', tmp_attribute_line_id.attribute_id.id)], limit=1)
                                    item_ids.append(value_id.id)

                            item_ids.sort()
                            product_pro_ids = self.env['product.product'].search(
                                                    [('product_tmpl_id', '=', pro_map_id.product_id.id)])
                            keys = []
                            true_keys = []
                            default_product = 0
                            for product_pro_id in product_pro_ids:
                                keys.sort()
                                if keys and item_ids == keys:
                                    default_product = default_pro_variant_id.id
                                    break

                                if true_keys and False not in true_keys:
                                    default_product = default_pro_variant_id.id

                                keys.clear()
                                true_keys.clear()
                                for attribute in product_pro_id.product_template_attribute_value_ids:
                                    default_pro_variant_id = product_pro_id
                                    keys.append(attribute.product_attribute_value_id.id)
                                    true_keys.append(attribute.product_attribute_value_id.is_default)

                            if default_product > 0:
                                order_line_list.append((0, 0, {
                                    'product_id': default_product,
                                    'qty': line_data['quantity'],
                                    'price_unit': line_data['displayable_original_price'] + addon_total_incl,
                                    'price_subtotal': line_data['final_price'],
                                    'price_subtotal_incl': line_data['displayable_final_price'],
                                }))
                        else:
                            product_pro_id  = self.env['product.product'].search(
                                                [('product_tmpl_id', '=', pro_map_id.product_id.id)], limit=1)
                            order_line_list.append((0, 0, {
                                'product_id': product_pro_id.id,
                                'qty': line_data['quantity'],
                                'price_unit': line_data['displayable_original_price'] + addon_total_incl,
                                'price_subtotal': line_data['final_price'],
                                'price_subtotal_incl': line_data['displayable_final_price'],
                            }))

        # Create delivery product Line
        if order_dic['delivery_price'] > 0:
            configuration_obj = self.env[
                'foodics.configuration'].search([], limit=1)
            delivery_product_id = configuration_obj.delivery_product_id
            if delivery_product_id:
                if not delivery_product_id.taxes_id:
                    tax_id = configuration_obj.excluded_taxes_id
                    delivery_product_id.product_tmpl_id.write({'taxes_id':[(6,0,[tax_id.id])]})

                order_line_list.append((0, 0, {
                    'product_id': delivery_product_id.id,
                    'qty': 1,
                    'price_unit': order_dic['delivery_price'],
                    'price_subtotal': order_dic['delivery_price'],
                    'price_subtotal_incl': order_dic['delivery_price'],
                }))
            else:
                product_id = self.env['product.product'].search([('name', '=', 'Delivery charges')], limit=1)
                configuration_obj.write({'delivery_product_id': product_id.id})
                if product_id:
                    if not product_id.taxes_id:
                        tax_id = configuration_obj.excluded_taxes_id
                        product_id.product_tmpl_id.write({'taxes_id':[(6,0,[tax_id.id])]})

                    order_line_list.append((0, 0, {
                        'product_id': product_id.id,
                        'qty': 1,
                        'price_unit': order_dic['delivery_price'],
                        'price_subtotal': order_dic['delivery_price'],
                        'price_subtotal_incl': order_dic['delivery_price'],
                    }))
        # Create discount product line
        if order_dic['discount_amount'] > 0:
            configuration_obj = self.env[
                'foodics.configuration'].search([], limit=1)
            discount_product_id = configuration_obj.discount_product_id
            if discount_product_id:
                if not discount_product_id.taxes_id:
                    tax_id = configuration_obj.excluded_taxes_id
                    discount_product_id.product_tmpl_id.write({'taxes_id':[(6,0,[tax_id.id])]})

                order_line_list.append((0, 0, {
                    'product_id': discount_product_id.id,
                    'qty': 1,
                    'price_unit': order_dic['discount_amount'] * -1,
                    'price_subtotal': order_dic['discount_amount'] * -1,
                    'price_subtotal_incl': order_dic['discount_amount'] * -1,
                }))
            else:
                product_id = self.env['product.product'].search([('name', '=', 'Discount')], limit=1)
                if not product_id:
                    product_id = product_obj.create({
                        'name': 'Discount',
                        'type': 'service',
                        'categ_id': 1,
                    })
                if product_id:
                    configuration_obj.write({'discount_product_id': product_id.id})
                    if not product_id.taxes_id:
                        tax_id = configuration_obj.excluded_taxes_id
                        product_id.product_tmpl_id.write({'taxes_id':[(6,0,[tax_id.id])]})

                    order_line_list.append((0, 0, {
                        'product_id': product_id.id,
                        'qty': 1,
                        'price_unit': order_dic['discount_amount'] * -1,
                        'price_subtotal': order_dic['discount_amount'] * -1,
                        'price_subtotal_incl': order_dic['discount_amount'] * -1,
                    }))

        return order_line_list

    def process_orders(self, history_obj, data):
        '''
        {
            "orders": [
               {
                  "guid": "FA135680-AA42-42D4-9370-69BD879122D8",
                  "reference": "QNWTB01C0132235",
                  "sequence": 32235,
                  "status": 4,
                  "type": 4,
                  "source": 1,
                  "persons": 1,
                  "notes": "",
                  "price": 36.19,
                  "delivery_price": 0,
                  "discount_amount": 0,
                  "final_price": 38,
                  "kitchen_received_at": "2020-03-30 12:45:46",
                  "kitchen_done_at": null,
                  "delay_in_seconds": 0,
                  "due_time": null,
                  "opened_at": "2020-03-30 12:45:14",
                  "closed_at": "2020-03-30 17:48:05",
                  "created_at": "2020-03-30 08:45:47",
                  "updated_at": "2020-03-30 13:48:05",
                  "address": "",
                  "number": 1,
                  "rounding": 0,
                  "driver_collected_at": null,
                  "delivered_at": null,
                  "kitchen_times": [

                  ],
                  "tips": 0,
                  "service_fees": 0,
                  "total_tax": 1.81,
                  "dispatched_at": null,
                  "hid": "_8g68991a45",
                  "void_reason": "",
                  "business_date": "2020-03-30",
                  "products": [
                    {
                      "guid": "B7587672-D712-420A-B692-603E84F68A95",
                      "status": 3,
                      "should_return_ingredients": false,
                      "quantity": 1,
                      "returned_quantity": 0,
                      "notes": "Only jalupino",
                      "original_price": 36.19,
                      "final_price": 36.19,
                      "kitchen_received_at": "2020-03-30 12:45:46",
                      "kitchen_done_at": null,
                      "actual_date": "2020-03-30 12:45:29",
                      "delay_in_seconds": 0,
                      "cost": 0,
                      "kitchen_times": [

                      ],
                      "discount_amount": 0,
                      "displayable_original_price": 38,
                      "displayable_final_price": 38,
                      "taxable": true,
                      "is_combo": false,
                      "hid": "_2ad985g998",
                      "void_reason": "",
                      "business_date": "2020-03-30",
                      "product_hid": "_722489g8",
                      "product_size_hid": "_7885a4a4",
                      "removed_ingredients": [

                      ],
                      "options": [
                        {
                          "hid": "_78daa5g7",
                          "costingType": "ingredients",
                          "relationship_data": {
                            "quantity": 1,
                            "final_price": 0,
                            "original_price": 0,
                            "cost": 0
                          }
                        }
                      ],
                      "discount": null,
                      "combo": null,
                      "combo_option_size": null
                    }
                  ],
                  "branch": {
                    "hid": "_27864a87",
                    "disabled_order_types": [

                    ]
                  },
                  "application": null,
                  "cashier": {
                    "hid": "_7652a147",
                    "pin": "*****"
                  },
                  "driver": null,
                  "waiter": null,
                  "online_orders_agent": null,
                  "device": {
                    "hid": "_a7g59d17"
                  },
                  "customer": {
                    "name": "Talabat",
                    "phone": "800117117",
                    "email": null,
                    "address": "",
                    "notes": "",
                    "blacklist": false,
                    "created_at": "2019-05-29 13:35:53",
                    "updated_at": "2019-05-29 13:35:53",
                    "hid": "_799561ga",
                    "country": {
                      "hid": "_1527947d"
                    }
                  },
                  "table": null,
                  "discount": null,
                  "payments": [
                    {
                      "guid": "6D703626-6E7C-461D-AE45-A3A4625112A0",
                      "amount": 38,
                      "tendered": 38,
                      "actual_date": "2020-03-30 17:48:05",
                      "details": "",
                      "created_at": "2020-03-30 13:48:05",
                      "updated_at": "2020-03-30 13:48:05",
                      "hid": "_225g946a9g",
                      "business_date": "2020-03-30",
                      "payment_method": {
                        "hid": "_7ad11547"
                      },
                      "employee": {
                        "hid": "_7652a147",
                        "pin": "*****"
                      }
                    }
                  ],
                  "delivery_address": {
                    "hid": "_7a899gag"
                  },
                  "taxes": [
                    {
                      "hid": "_67ad6a37",
                      "relationship_data": {
                        "amount": 1.81,
                        "percentage": 5
                      }
                    }
                  ],
                  "tags": [

                  ]
                }
        }
        '''
        history_obj.write({'status': 'inprocess'})
        pos_order_obj = self.env['pos.order']
        pos_order_line_obj = self.env['pos.order.line']
        order_mapping_obj = self.env['foodics.orders.mapping']
        get_data_in_dic = json.loads(data)
        order_li = get_data_in_dic['orders']

        if order_li:
            for order_dic in order_li:
                if 'reference' in order_dic and order_dic['status'] == 4:
                #if order_dic['reference'] == 'QNWTB03C012711600001':
                    order_id = pos_order_obj.search(
                        [('foodic_name', '=', order_dic['reference'])])
                    _logger.info("== order ref in process == %s", order_dic['reference'])
                    if not order_id:
                        # Search Branch
                        branch_mapping_id = self.env['foodics.branch.mapping'].search([
                            ('branch_foodics_id', '=', order_dic['branch']['hid'])])
                        if branch_mapping_id:
                            picking_type_id = self.env['stock.picking.type'].search([
                                ('name', '=', 'PoS Orders'),
                              ('warehouse_id', '=', branch_mapping_id.branch_id.id)], limit=1)
                            pos_config_id = self.env['pos.config'].search([
                                ('picking_type_id', '=', picking_type_id.id)], limit=1)

                            # PoS session search or create
                            session_id = self.get_pos_session(
                                pos_config_id.id, order_dic['business_date'])

                        # Search or Create Customer
                        if order_dic['customer']:
                            hid = order_dic['customer']['hid']
                            partner_name = order_dic['customer']['name']
                            customer_dic = order_dic['customer']
                            partner_id = self.get_pos_customer(
                                hid, partner_name, customer_dic)
                        else:
                            partner_id = False

                        # Search or Create Payment Method
                        amount_paid = 0
                        payment_list = []
                        if order_dic['payments']:
                            for payment_data in order_dic['payments']:
                                payment_mapping_id = self.env['foodics.payment.method.mapping'].search([
                                    ('payment_foodics_id', '=', payment_data['payment_method']['hid'])])
                                if payment_mapping_id:
                                    amount_paid = payment_data['amount']
                                    payment_list.append((0, 0, {
                                        'amount': payment_data['amount'],
                                        'payment_date': payment_data['actual_date'],
                                        'payment_method_id': payment_mapping_id.payment_id.id,
                                    }))

                        # Add Order lines
                        order_lines = self.get_order_line(order_dic)

                        # Create Order
                        order_id = pos_order_obj.create({
                            'foodic_name': order_dic['reference'],
                            'session_id': session_id.id,
                            'partner_id': partner_id.id if partner_id else False,
                            'note': order_dic['notes'],
                            'date_order': str(order_dic['created_at']),
                            'lines': order_lines,
                            'payment_ids': payment_list,
                            'amount_tax': 1,
                            'amount_total': 1,
                            'amount_paid': 1,
                            'amount_return': 1,
                        })
                        # Update line data
                        for line_id in order_id.lines:
                            line_qty = line_id.qty
                            line_price_unit = line_id.price_unit
                            line_price_subtotal = line_id.price_subtotal
                            line_price_subtotal_incl = line_id.price_subtotal_incl

                            line_id._onchange_product_id()
                            line_id.write({
                                'qty': line_qty,
                                'price_unit': line_price_unit,
                                'price_subtotal': line_price_subtotal,
                                'price_subtotal_incl': line_price_subtotal_incl,
                            })
                            line_id._onchange_amount_line_all()

                            if line_id.price_subtotal_incl != line_price_subtotal_incl:
                                line_id.write({"price_subtotal_incl": line_price_subtotal_incl})

                        order_id._onchange_amount_all()
                        # Adjustment for unbalanced amount
                        if order_id.amount_total != order_id.amount_paid:
                            adjustment_amount = order_id.amount_total - order_id.amount_paid
                            if adjustment_amount < 1 and adjustment_amount > -1:
                                configuration_obj = self.env[
                                    'foodics.configuration'].search([], limit=1)
                                adjustment_product_id = configuration_obj.adjustment_product_id
                                if adjustment_product_id:
                                    new_line = order_id.lines.create({
                                        'order_id': order_id.id,
                                        'product_id': adjustment_product_id.id,
                                        'qty': 1,
                                        'price_unit': float(adjustment_amount) * -1,
                                        'price_subtotal': float(adjustment_amount) * -1,
                                        'price_subtotal_incl': float(adjustment_amount) * -1,
                                    })
                                    order_id._onchange_amount_all()
                                    order_id.action_pos_order_paid()
                        else:
                            order_id.action_pos_order_paid()

                        # if order_id.amount_total == order_id.amount_paid:
                        #     order_id.action_pos_order_paid()

                        #_logger.info("== Amount diff between total and paid %s %s", order_dic['reference'], order_id.amount_total - order_id.amount_paid)

                        # Create mapping record for order
                        mapping_rec_id = order_mapping_obj.create({
                            'order_id': order_id.id,
                            'order_odoo_id': order_id.id,
                            'order_foodics_id': order_dic['hid'],
                            'foodics_created_date': order_dic['created_at'],
                            'foodics_update_date': order_dic['updated_at'],
                        })
                        history_obj.write({'status': 'done'})
                        #self._cr.commit()
                    else:
                        order_mapping_id = order_mapping_obj.search(
                            [('order_id', '=', order_id.id)])
                        if not order_mapping_id:
                            mapping_rec_id = order_mapping_obj.create({
                                'order_id': order_id.id,
                                'order_odoo_id': order_id.id,
                                'order_foodics_id': order_dic['hid'],
                                'foodics_created_date': order_dic['created_at'],
                                'foodics_update_date': order_dic['updated_at'],
                            })
                        history_obj.write({'status': 'done'})
                else:
                    history_obj.write({'status': 'exceptions',
                                       'fail_reason': 'No data or some order status is not done'})
        else:
            history_obj.write({'status': 'exceptions',
                               'fail_reason': 'No data to process'})