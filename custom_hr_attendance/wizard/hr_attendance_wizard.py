# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from odoo.tools.translate import _
from odoo.tools import email_split
from odoo.exceptions import UserError

from odoo import api, fields, models
import pytz
import sys
import datetime
import logging
import binascii

from odoo.addons.hr_zk_attendance.models import zklib
from odoo.addons.hr_zk_attendance.models.zkconst import *
from struct import unpack


_logger = logging.getLogger(__name__)

class HrAttendance(models.Model):
    _inherit = "hr.attendance"

    @api.constrains('check_in', 'check_out', 'employee_id')
    def _check_validity(self):
        print("=====inherit main att===")
        """ Verifies the validity of the attendance record compared to the others from the same employee.
            For the same employee we must have :
                * maximum 1 "open" attendance record (without check_out)
                * no overlapping time slices with previous employee records
        """
        for attendance in self:
            # we take the latest attendance before our check_in time and check it doesn't overlap with ours
            last_attendance_before_check_in = self.env['hr.attendance'].search([
                ('employee_id', '=', attendance.employee_id.id),
                ('check_in', '<=', attendance.check_in),
                ('id', '!=', attendance.id),
            ], order='check_in desc', limit=1)
            print("===last_attendance_before_check_in====", last_attendance_before_check_in)
            print("===last_attendance_before_check_in====", last_attendance_before_check_in)
            print("===attendance.check_in====", attendance.check_in)
            print("===attendance.check_out====", attendance.check_out)
            if last_attendance_before_check_in and last_attendance_before_check_in.check_out and last_attendance_before_check_in.check_out > attendance.check_in:
                raise exceptions.ValidationError(_("Cannot create new attendance record for %(empl_name)s, the employee was already checked in on %(datetime)s") % {
                    'empl_name': attendance.employee_id.name,
                    'datetime': fields.Datetime.to_string(fields.Datetime.context_timestamp(self, fields.Datetime.from_string(attendance.check_in))),
                })

            if not attendance.check_out:
                # if our attendance is "open" (no check_out), we verify there is no other "open" attendance
                print("====if attendance=====", attendance)
                no_check_out_attendances = self.env['hr.attendance'].search([
                    ('employee_id', '=', attendance.employee_id.id),
                    ('check_out', '=', False),
                    ('id', '!=', attendance.id),
                ], order='check_in desc', limit=1)
                if no_check_out_attendances:
                    raise exceptions.ValidationError(_("Cannot create new attendance record for %(empl_name)s, the employee hasn't checked out since %(datetime)s") % {
                        'empl_name': attendance.employee_id.name,
                        'datetime': fields.Datetime.to_string(fields.Datetime.context_timestamp(self, fields.Datetime.from_string(no_check_out_attendances.check_in))),
                    })
            else:
                # we verify that the latest attendance with check_in time before our check_out time
                # is the same as the one before our check_in time computed before, otherwise it overlaps
                last_attendance_before_check_out = self.env['hr.attendance'].search([
                    ('employee_id', '=', attendance.employee_id.id),
                    ('check_in', '<', attendance.check_out),
                    ('id', '!=', attendance.id),
                ], order='check_in desc', limit=1)
                print("=======last_attendance_before_check_out======", last_attendance_before_check_out)
                # if last_attendance_before_check_out and last_attendance_before_check_in != last_attendance_before_check_out:
                #     print("====elif if attendance=====", attendance)
                #     raise exceptions.ValidationError(_("Cannot create new attendance record for %(empl_name)s, the employee was already checked in on %(datetime)s") % {
                #         'empl_name': attendance.employee_id.name,
                #         'datetime': fields.Datetime.to_string(fields.Datetime.context_timestamp(self, fields.Datetime.from_string(last_attendance_before_check_out.check_in))),
                #     })


class ZkAttendanceWizard(models.TransientModel):

    _name = 'zk.attendance.wizard'
    _description = 'Zk Attendance Wizard'

    name = fields.Char(string="Domain Name",required=True)
    port = fields.Integer(string="Port No", required=True)
    date = fields.Date(string="Date")
    from_date = fields.Date(string="From Date")
    to_date = fields.Date(string="To date")
    type_date = fields.Selection(string="Type", default='p_date', selection=[('p_date', "Particular Date"), ('in_between_date', "In between date")])

    def get_attendance_data(self):
        _logger.info("++++++++++++++++++++++++++++++++++")
        zk_attendance = self.env['zk.machine.attendance']
        att_obj = self.env['hr.attendance']
        zk_machine_obj = self.env['zk.machine']
        
        machine_ip = self.name
        port = self.port
        print("===machine_ip===", machine_ip)
        print("===port===", port)
        zk = zklib.ZKLib(machine_ip, port)
        print("====zk====", zk)
        conn = zk_machine_obj.device_connect(zk)
        print("=====conn==", conn)
        if conn:
            zk.enableDevice()
            user = zk_machine_obj.zkgetuser(zk)
            print("========",user)
            command = CMD_ATTLOG_RRQ
            command_string = ''
            chksum = 0
            session_id = zk.session_id
            reply_id = unpack('HHHH', zk.data_recv[:8])[3]
            buf = zk.createHeader(command, chksum, session_id,
                                    reply_id, command_string)
            zk.zkclient.sendto(buf, zk.address)
            print("====buf, zk.address========", buf, zk.address)
            try:
                zk.data_recv, addr = zk.zkclient.recvfrom(1024)
                command = unpack('HHHH', zk.data_recv[:8])[0]
                if command == CMD_PREPARE_DATA:
                    size = unpack('I', zk.data_recv[8:12])[0]
                    zk_size = size
                else:
                    zk_size = False
                if zk_size:
                    bytes = zk_size
                    while bytes > 0:
                        data_recv, addr = zk.zkclient.recvfrom(1032)
                        zk.attendancedata.append(data_recv)
                        bytes -= 1024
                    zk.session_id = unpack('HHHH', zk.data_recv[:8])[2]
                    data_recv = zk.zkclient.recvfrom(8)
                attendance = []
                if len(zk.attendancedata) > 0:
                    # The first 4 bytes don't seem to be related to the user
                    for x in range(len(zk.attendancedata)):
                        if x > 0:
                            zk.attendancedata[x] = zk.attendancedata[x][8:]
                    attendancedata = b''.join(zk.attendancedata) 
                    attendancedata = attendancedata[14:] 
                    while len(attendancedata) > 0:
                        uid, state, timestamp, space = unpack('24s1s4s11s', attendancedata.ljust(40)[:40])
                        pls = unpack('c', attendancedata[29:30])
                        uid = uid.split(b'\x00', 1)[0].decode('utf-8')
                        tmp = ''
                        for i in reversed(range(int(len(binascii.hexlify(timestamp)) / 2))):
                            tmp += binascii.hexlify(timestamp).decode('utf-8')[i * 2:(i * 2) + 2] 
                        attendance.append((uid, int(binascii.hexlify(state), 16),
                                            decode_time(int(tmp, 16)), unpack('HHHH', space[:8])[0]))
                        
                        attendancedata = attendancedata[40:]
            except Exception as e:
                _logger.info("++++++++++++Exception++++++++++++++++++++++", e)
                attendance = False
            if attendance:
                for each in attendance:
                    atten_time = each[2]
                    atten_time = datetime.strptime(
                        atten_time.strftime('%Y-%m-%d %H:%M:%S'), '%Y-%m-%d %H:%M:%S')
                    local_tz = pytz.timezone(
                        self.env.user.partner_id.tz or 'GMT')
                    local_dt = local_tz.localize(atten_time, is_dst=None)
                    utc_dt = local_dt.astimezone(pytz.utc)
                    utc_dt = utc_dt.strftime("%Y-%m-%d %H:%M:%S")
                    atten_time = datetime.strptime(
                        utc_dt, "%Y-%m-%d %H:%M:%S")
                    atten_time = fields.Datetime.to_string(atten_time)
                    if user:
                        for uid in user:
                            if user[uid][0] == str(each[0]):
                                get_user_id = self.env['hr.employee'].search(
                                    [('device_id', '=', str(each[0]))])
                                if get_user_id:
                                    duplicate_atten_ids = zk_attendance.search(
                                        [('device_id', '=', str(each[0])), ('punching_time', '=', atten_time)])
                                    if duplicate_atten_ids:
                                        continue
                                    else:
                                        zk_attendance.create({'employee_id': get_user_id.id,
                                                                'device_id': each[0],
                                                                'attendance_type': str(each[1]),
                                                                'punch_type': str(each[3]),
                                                                'punching_time': atten_time,
                                                                'address_id': info.address_id.id})
                                        att_var = att_obj.search([('employee_id', '=', get_user_id.id),
                                                                    ('check_out', '=', False)])
                                        if each[3] == 0: #check-in
                                            if not att_var:
                                                att_obj.create({'employee_id': get_user_id.id,
                                                                'check_in': atten_time})
                                        if each[3] == 1: #check-out
                                            if len(att_var) == 1:
                                                att_var.write({'check_out': atten_time})
                                            else:
                                                att_var1 = att_obj.search([('employee_id', '=', get_user_id.id)])
                                                if att_var1:
                                                    att_var1[-1].write({'check_out': atten_time})

                                else:
                                    employee = self.env['hr.employee'].create(
                                        {'device_id': str(each[0]), 'name': user[uid][1]})
                                    try:
                                        zk_attendance.create({'employee_id': employee.id,
                                                            'device_id': each[0],
                                                            'attendance_type': str(each[1]),
                                                            'punch_type': str(each[3]),
                                                            'punching_time': atten_time,
                                                            'address_id': info.address_id.id})
                                    except Exception as e:
                                        _logger.info("++++++++++++Att Exception++++++++++++++++++++++", e)
                                    att_obj.create({'employee_id': employee.id,
                                                    'check_in': atten_time})
                            else:
                                pass
                zk.enableDevice()
                zk.disconnect()
                return True
            else:
                raise UserError(_('Unable to get the attendance log, please try again later.'))
        else:
            raise UserError(_('Unable to connect, please check the parameters and network connections.'))


