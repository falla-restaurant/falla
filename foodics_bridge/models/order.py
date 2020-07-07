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
                count = count + 1
            if count > 1:
                raise ValidationError(
                    "You can select only one default attribute value")
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

            response = requests.request(
                "GET", url, headers=headers, data=payload)

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
                except Exception as e:
                    _logger.info("Session close fail", e)

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
            customer_mapping_obj.create({
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

    def remove_unmatched_orders(self, order_id):
        _logger.info("== Called remove_unmatched_orders %s", order_id)
        line_obj = self.env['pos.order.line']
        payment_obj = self.env['pos.payment']
        mapping_obj = self.env['foodics.orders.mapping']

        if order_id:
            payment_ids = payment_obj.search(
                [('pos_order_id', '=', order_id.id)])
            for payment_id in payment_ids:
                payment_id.unlink()

            mapping_ids = mapping_obj.search([('order_id', '=', order_id.id)])
            for mapping_id in mapping_ids:
                mapping_id.unlink()

            line_ids = line_obj.search([('order_id', '=', order_id.id)])
            for line_id in line_ids:
                line_id.unlink()

            order_id.unlink()
            
    def check_session_valid(self, business_date, session_id, order_obj, pos_config_id, session_obj):
        _logger.info("== Called check_session_valid ==")
        dt = datetime.datetime.strptime(
            str(session_id.start_at), '%Y-%m-%d %H:%M:%S')

        if str(dt.date()) == str(business_date):
            return session_id
        else:
            pos_orders = order_obj.search(
                [('session_id', '=', session_id.id)])
            for order_id in pos_orders:
                if order_id.state == 'draft':
                    if round(order_id.amount_total, 2) == round(order_id.amount_paid, 2):
                        order_id.action_pos_order_paid()
                    else:
                        if order_id.amount_total != order_id.amount_paid:
                            self.check_adjustment_amount(order_id)
                            
            _logger.info("==session status== %s", session_id.state)
            session_id.action_pos_session_closing_control()
            _logger.info(
                "==session status after close call== %s", session_id.state)

            session_id = session_obj.create({
                'user_id': self.env.uid,
                'config_id': pos_config_id,
                'start_at': str(business_date),
            })
            return session_id

    def get_pos_session(self, pos_config_id, business_date):
        # session date should be business date
        _logger.info("Called get_pos_session")
        session_obj = self.env['pos.session']
        order_obj = self.env['pos.order']
        
        session_id = session_obj.search([
            ('config_id', '=', pos_config_id),
            ('state', 'in', ('new_session', 'opened'))], limit=1)
        _logger.info("get_pos_session -> session_id %s config_id %s",
                     session_id, pos_config_id)
        if session_id:
            session_id = self.check_session_valid(business_date, session_id, order_obj, pos_config_id, session_obj)
            return session_id
        else:
            # check if any session open for this user and conf - close if any
            open_session_res = session_obj.search([('user_id', '=', self.env.uid),
                                                   ('config_id', '=',
                                                    pos_config_id),
                                                   ('state', 'in', ['opened', 'closing_control'])])
            _logger.info("== open_session_res == %s", open_session_res)
            for open_session_id in open_session_res:
                pos_orders = order_obj.search(
                    [('session_id', '=', open_session_id.id)])
                for order_id in pos_orders:
                    if order_id.state == 'draft':
                        if round(order_id.amount_total, 2) == round(order_id.amount_paid, 2):
                            order_id.action_pos_order_paid()
                        else:
                            if order_id.amount_total != order_id.amount_paid:
                                self.check_adjustment_amount(order_id)

                _logger.info("==session status== %s", open_session_id.state)
                open_session_id.action_pos_session_closing_control()
                _logger.info(
                    "==session status after close call== %s", open_session_id.state)

            session_id = session_obj.create({
                'user_id': self.env.uid,
                'config_id': pos_config_id,
                'start_at': business_date,
            })
            _logger.info("== New created session id -> %s", session_id)
            return session_id
        
    def create_delivery_line(self, product_obj, order_dic):
        _logger.info("== Called create_delivery_line")
        order_line_dic = {
            'qty': 1,
            'price_unit': order_dic['delivery_price'],
            'price_subtotal': order_dic['delivery_price'],
            'price_subtotal_incl': order_dic['delivery_price'],
        }
        configuration_obj = self.env[
                'foodics.configuration'].search([], limit=1)
        delivery_product_id = configuration_obj.delivery_product_id
        if delivery_product_id:
            if not delivery_product_id.taxes_id:
                tax_id = configuration_obj.excluded_taxes_id
                delivery_product_id.product_tmpl_id.write(
                    {'taxes_id': [(6, 0, [tax_id.id])]})

            order_line_dic['product_id'] = delivery_product_id.id
        else:
            product_id = product_obj.search(
                [('name', '=', 'Delivery charges')], limit=1)
            configuration_obj.write({'delivery_product_id': product_id.id})
            if product_id:
                if not product_id.taxes_id:
                    tax_id = configuration_obj.excluded_taxes_id
                    product_id.product_tmpl_id.write(
                        {'taxes_id': [(6, 0, [tax_id.id])]})

                order_line_dic['product_id'] = product_id.id
        return order_line_dic
    
    def create_discount_line(self, product_obj, order_dic):
        _logger.info("== Called create_discount_line")
        order_line_dic = {
            'qty': 1,
            'price_unit': order_dic['discount_amount'] * -1,
            'price_subtotal': order_dic['discount_amount'] * -1,
            'price_subtotal_incl': order_dic['discount_amount'] * -1,
        }
        configuration_obj = self.env[
                'foodics.configuration'].search([], limit=1)
        discount_product_id = configuration_obj.discount_product_id
        if discount_product_id:
            if not discount_product_id.taxes_id:
                tax_id = configuration_obj.excluded_taxes_id
                discount_product_id.product_tmpl_id.write(
                    {'taxes_id': [(6, 0, [tax_id.id])]})

            order_line_dic['product_id'] = discount_product_id.id
        else:
            product_id = product_obj.search(
                [('name', '=', 'Discount')], limit=1)
            if not product_id:
                product_id = product_obj.create({
                    'name': 'Discount',
                    'type': 'service',
                    'categ_id': 1,
                })
            if product_id:
                configuration_obj.write(
                    {'discount_product_id': product_id.id})
                if not product_id.taxes_id:
                    tax_id = configuration_obj.excluded_taxes_id
                    product_id.product_tmpl_id.write(
                        {'taxes_id': [(6, 0, [tax_id.id])]})

                order_line_dic['product_id'] = product_id.id
        return order_line_dic
    
    def create_line_for_no_option(self, pro_map_id, line_data, product_obj):
        _logger.info("== Called create_line_for_no_option")
        order_line_dic = {
            'qty': line_data['quantity'],
            'price_unit': line_data['displayable_original_price'],
            'price_subtotal': line_data['final_price'],
            'price_subtotal_incl': line_data['displayable_final_price'],
        }
        product_pro_ids = product_obj.search(
            [('product_tmpl_id', '=', pro_map_id.product_id.id)])
        product_id = 0
        for product_pro_id in product_pro_ids:
            for attribute in product_pro_id.product_template_attribute_value_ids:
                product_id = product_pro_id.id
                if not attribute.product_attribute_value_id.is_default:
                    product_id = 0
                    break
            if product_id:
                break
        if product_id:
            order_line_dic['product_id'] = product_id
        else:
            order_line_dic['product_id'] = product_pro_ids[0].id
        return order_line_dic
    
    def create_line_for_modifiers(self, pro_map_id, line_data, product_obj):
        _logger.info("== Called create_line_for_modifiers")
        
        item_ids = []
        modifier_ids = []
        addon_total = 0.0
        for oprtion_data in line_data['options']:

            if oprtion_data['relationship_data']:
                addon_qty = oprtion_data['relationship_data']['quantity']
                addon_amount = round(oprtion_data['relationship_data']['original_price'], 3) * addon_qty
                addon_total = float(addon_total) + float(addon_amount)

            modifier_option_id = self.env['modifier.value'].search(
                [('option_foodics_id', '=', oprtion_data['hid'])])
            if modifier_option_id:
                modifier_ids.append(
                    modifier_option_id.modifier_id.product_id.id)
                for items in modifier_option_id.modifier_id.product_id.value_ids:
                    if items.name == modifier_option_id.name:
                        item_ids.append(items.id)

        if addon_total > 0:
            addon_total_incl = (
                addon_total / 10) / 2 + addon_total
        else:
            addon_total_incl = 0
            
        order_line_dic = {
            'qty': line_data['quantity'],
            'price_unit': line_data['displayable_original_price'] + addon_total_incl,
            'price_subtotal': line_data['final_price'],
            'price_subtotal_incl': line_data['displayable_final_price'],
        }

        product_pro_ids = product_obj.search(
                [('product_tmpl_id', '=', pro_map_id.product_id.id)])
        if pro_map_id.product_id.attribute_line_ids:
            for tmp_attribute_line_id in pro_map_id.product_id.attribute_line_ids:
                if tmp_attribute_line_id.attribute_id.id not in modifier_ids:
                    value_id = self.env['product.attribute.value'].search(
                        [('is_default', '=', True),
                         ('attribute_id', '=', tmp_attribute_line_id.attribute_id.id)], limit=1)
                    item_ids.append(value_id.id)
            item_ids.sort()
            
            product_id = 0
            for product_pro_id in product_pro_ids:
                keys = []
                for attribute in product_pro_id.product_template_attribute_value_ids:
                    product_id = product_pro_id.id
                    keys.append(
                        attribute.product_attribute_value_id.id)
                    keys.sort()
                    if keys != item_ids:
                        product_id = 0
                        break
                if product_id:
                    break
            if product_id:
                order_line_dic['product_id'] = product_id
            else:
                order_line_dic['product_id'] = product_pro_ids[0].id
        else:
            order_line_dic['product_id'] = product_pro_ids[0].id
        return order_line_dic
        
    def get_order_line(self, order_dic):
        _logger.info("== Called get_order_line")
        product_obj = self.env['product.product']
        order_line_list = []
        # Create order Line
        for line_data in order_dic['products']:
            if not line_data['void_reason']:
                pro_map_id = self.env['foodics.product.mapping'].search([
                    ('product_foodics_id', '=', line_data['product_hid'])])
                _logger.info("== Product Mapping ID %s %s",
                             pro_map_id, line_data['product_hid'])
                if pro_map_id:
                    if pro_map_id.product_id.active == False:
                        pro_map_id.product_id.write({'active': True})
                    if not line_data['options']:
                        order_line_dic = self.create_line_for_no_option(pro_map_id, line_data, product_obj)
                        order_line_list.append((0, 0, order_line_dic))
                    else:
                        # if we have modifier in options
                        order_line_dic = self.create_line_for_modifiers(pro_map_id, line_data, product_obj)
                        order_line_list.append((0, 0, order_line_dic))
                        
        # Create delivery product Line
        if order_dic['delivery_price'] > 0:
            order_line_dic = self.create_delivery_line(product_obj, order_dic)
            order_line_list.append((0, 0, order_line_dic))
            
        # Create discount product line
        if order_dic['discount_amount'] > 0:
            order_line_dic = self.create_discount_line(product_obj, order_dic)
            order_line_list.append((0, 0, order_line_dic))

        return order_line_list

    def process_foodic_order(self, order_dic):
        foodic_pos_history_obj = self.env['foodics.pos.history']

        foodic_order_res = foodic_pos_history_obj.search(
            [('api_type', '=', 'PoS_Orders'),
             ('foodic_order_ref', '=', order_dic['reference'])])

        _logger.info("== Called process_foodic_order %s %s",
                     foodic_order_res, order_dic['reference'])
        
        if not foodic_order_res:
            foo_pos_order_res = foodic_pos_history_obj.create({
                'api_type': 'PoS_Orders',
                'response': json.dumps(order_dic),
                'status': 'draft',
                'foodic_order_ref': order_dic['reference'],
            })
            foo_pos_order_res.write({'status': 'inprocess'})
            # Call check_order_valid
            self.check_order_valid(foo_pos_order_res, order_dic)
        else:
            if foodic_order_res.status == 'draft':
                self.check_order_valid(foodic_order_res, order_dic)
                
    def check_branch(self, foo_pos_order_res, order_dic):
        _logger.info("== Called check_branch ==")
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
            return session_id
        else:
            foo_pos_order_res.write({'status': 'exceptions',
                                     'fail_reason': 'Amount tolal and amount paid are different.'})

    def check_customer(self, order_dic):
        _logger.info("== Called check_customer ==")
        partner_id = False
        if order_dic['customer']:
            hid = order_dic['customer']['hid']
            partner_name = order_dic['customer']['name']
            customer_dic = order_dic['customer']
            partner_id = self.get_pos_customer(
                hid, partner_name, customer_dic)
        return partner_id
    
    def check_payment(self, order_dic):
        _logger.info("== Called check_payment ==")
        payment_list = []
        if order_dic['payments']:
            for payment_data in order_dic['payments']:
                payment_mapping_id = self.env['foodics.payment.method.mapping'].search([
                    ('payment_foodics_id', '=', payment_data['payment_method']['hid'])])
                if payment_mapping_id:
                    payment_list.append((0, 0, {
                        'amount': payment_data['amount'],
                        'payment_date': payment_data['actual_date'],
                        'payment_method_id': payment_mapping_id.payment_id.id,
                    }))
        return payment_list
    
    def process_line_onchanges(self, order_id):
        _logger.info("== Called process_line_onchanges ==")
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
                
    def check_adjustment_amount(self, order_id):
        _logger.info("== Called check_adjustment_amount ==")
        history_res = self.env['foodics.pos.history'].search(
                        [('api_type', '=', 'PoS_Orders'),
                         ('status', 'in', [
                             'draft', 'inprocess']),
                         ('foodic_order_ref', '=', order_id.foodic_name)])
        adjustment_amount = order_id.amount_total - order_id.amount_paid
        if adjustment_amount < 1 and adjustment_amount > -1:
            configuration_obj = self.env[
                'foodics.configuration'].search([], limit=1)
            adjustment_product_id = configuration_obj.adjustment_product_id
            if adjustment_product_id:
                order_id.lines.create({
                    'order_id': order_id.id,
                    'product_id': adjustment_product_id.id,
                    'qty': 1,
                    'price_unit': float(adjustment_amount) * -1,
                    'price_subtotal': float(adjustment_amount) * -1,
                    'price_subtotal_incl': float(adjustment_amount) * -1,
                })
                order_id._onchange_amount_all()
                try:
                    order_id.action_pos_order_paid()
                    for history_id in history_res:
                        history_id.write(
                            {'status': 'done'})
                    #foo_pos_order_res.write({'status': 'done'})
                except Exception as e:
                    #for history_id in history_res:
                    history_id.write({'status': 'exceptions',
                                        'fail_reason': str(e)})
        else:
            self.remove_unmatched_orders(order_id)
            for history_id in history_res:
                history_id.write({'status': 'exceptions',
                                  'fail_reason': 'Amount tolal and amount paid are different.'})
            # foo_pos_order_res.write({'status': 'exceptions',
            #                          'fail_reason': 'Amount tolal and amount paid are different.'})
        
    def create_mapping_record(self, order_id, order_dic):
        self.env['foodics.orders.mapping'].create({
            'order_id': order_id.id,
            'order_odoo_id': order_id.id,
            'order_foodics_id': order_dic['hid'],
            'foodics_created_date': order_dic['created_at'],
            'foodics_update_date': order_dic['updated_at'],
        })
            
    def check_order_valid(self, foo_pos_order_res, order_dic):
        pos_order_obj = self.env['pos.order']
        order_mapping_obj = self.env['foodics.orders.mapping']
        # if order_dic['reference'] == 'QNWTB03C012711600001':
        if 'reference' in order_dic and order_dic['status'] == 4:
            order_id = pos_order_obj.search(
                [('foodic_name', '=', order_dic['reference'])])
            if not order_id:
                # Search Branch
                session_id = self.check_branch(foo_pos_order_res, order_dic)

                # Search or Create Customer
                partner_id = self.check_customer(order_dic)
                
                # Search or Create Payment Method
                payment_list = self.check_payment(order_dic)

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
                self.process_line_onchanges(order_id)
                
                # Call Order Onchanges
                order_id._onchange_amount_all()
                
                # Adjustment for unbalanced amount
                if order_id.amount_total != order_id.amount_paid:
                    self.check_adjustment_amount(order_id)
                else:
                    try:
                        order_id.action_pos_order_paid()
                        foo_pos_order_res.write({'status': 'done'})
                        # Create mapping record for order
                        self.create_mapping_record(order_id, order_dic)
                        
                    except Exception as e:
                        foo_pos_order_res.write({'status': 'exceptions',
                                                 'fail_reason': str(e)})
            else:
                order_mapping_id = order_mapping_obj.search(
                    [('order_id', '=', order_id.id)])
                if not order_mapping_id:
                    self.create_mapping_record(order_id, order_dic)
                foo_pos_order_res.write({'status': 'done'})
        else:
            foo_pos_order_res.write({'status': 'exceptions',
                                     'fail_reason': 'No data or some order status is not done'})

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
        get_data_in_dic = json.loads(data)
        order_li = get_data_in_dic['orders']

        if order_li:
            for order_dic in order_li:
                self.process_foodic_order(order_dic)
            history_obj.write({'status': 'done'})
        else:
            history_obj.write({'status': 'exceptions',
                               'fail_reason': 'No data to process'})
