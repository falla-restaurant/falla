# -*- coding: utf-8 -*-

import pytz
import sys
import logging
import binascii
import datetime
from datetime import timedelta

from . import zklib
from .zkconst import *
from struct import unpack
from odoo import api, fields, models
from odoo import _
from odoo.exceptions import UserError, ValidationError


_logger = logging.getLogger(__name__)


class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    device_id = fields.Char(string='Biometric Device ID')


class ZkMachine(models.Model):
    _name = 'zk.machine'

    name = fields.Char(string='Machine IP', required=True)
    port_no = fields.Integer(string='Port No', required=True)
    address_id = fields.Many2one('res.partner', string='Working Address')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.user.company_id.id)
    connection_type = fields.Selection([('connection_1', 'Connection 1'),
                                    ('connection_2', 'Connection 2')], default='connection_1', string='Connection Type')


    def device_connect(self, zk):
        command = CMD_CONNECT
        command_string = ''
        chksum = 0
        session_id = 0
        reply_id = -1 + USHRT_MAX
        buf = zk.createHeader(command, chksum, session_id,
                              reply_id, command_string)
        zk.zkclient.sendto(buf, zk.address)
        try:
            zk.data_recv, addr = zk.zkclient.recvfrom(1024)
            zk.session_id = unpack('HHHH', zk.data_recv[:8])[2]
            command = unpack('HHHH', zk.data_recv[:8])[0]
            print("============commanddd====", command)
            if command == 2005:
                conn = True
            else:
                conn = False
        except:
            conn = False
        return conn

    # def clear_attendance(self):
    #     for info in self:
    #         try:
    #             machine_ip = info.name
    #             port = info.port_no
    #             zk = zklib.ZKLib(machine_ip, port)
    #             conn = self.device_connect(zk)
    #             if conn:
    #                 zk.enableDevice()
    #                 clear_data = zk.getAttendance()
    #                 if clear_data:
    #                     zk.clearAttendance()
    #                     self._cr.execute("""delete from zk_machine_attendance""")
    #                 else:
    #                     raise UserError(_('Unable to get the attendance log, please try again later.'))
    #             else:
    #                 raise UserError(_('Unable to connect, please check the parameters and network connections.'))
    #         except:
    #             raise ValidationError('Warning !!! Machine is not connected')

    def getSizeUser(self, zk):
        """Checks a returned packet to see if it returned CMD_PREPARE_DATA,
        indicating that data packets are to be sent

        Returns the amount of bytes that are going to be sent"""
        command = unpack('HHHH', zk.data_recv[:8])[0]
        if command == CMD_PREPARE_DATA:
            size = unpack('I', zk.data_recv[8:12])[0]
            print("size", size)
            return size
        else:
            return False

    def zkgetuser(self, zk):
        """Start a connection with the time clock"""
        command = CMD_USERTEMP_RRQ
        command_string = '\x05'
        chksum = 0
        session_id = zk.session_id
        reply_id = unpack('HHHH', zk.data_recv[:8])[3]
        buf = zk.createHeader(command, chksum, session_id, reply_id, command_string)
        zk.zkclient.sendto(buf, zk.address)

        try:
            zk.data_recv, addr = zk.zkclient.recvfrom(1024)
            if self.getSizeUser(zk):

                bytes = self.getSizeUser(zk)
                while bytes > 0:
                    data_recv, addr = zk.zkclient.recvfrom(1032)
                    zk.userdata.append(data_recv)
                    bytes -= 1024

                zk.session_id = unpack('HHHH', zk.data_recv[:8])[2]
                data_recv = zk.zkclient.recvfrom(8)

            users = {}
            if len(zk.userdata) > 0:
                for x in range(len(zk.userdata)):
                    if x > 0:
                        zk.userdata[x] = zk.userdata[x][8:]
                userdata = b''.join(zk.userdata)
                userdata = userdata[11:]
                while len(userdata) > 72:
                    uid, role, password, name, userid = unpack('2s2s8s28sx31s', userdata.ljust(72)[:72])
                    uid = int(binascii.hexlify(uid), 16)
                    # print("uid",uid)
                    # Clean up some messy characters from the user name
                    password = password.split(b'\x00', 1)[0]
                    password = str(password.strip(b'\x00|\x01\x10x|\x000').decode('utf-8'))
                    # uid = uid.split('\x00', 1)[0]
                    userid = str(userid.strip(b'\x00|\x01\x10x|\x000|\x9aC').decode('utf-8'))
                    name = name.split(b'\x00', 1)[0].decode('utf-8')
                    if name.strip() == "":
                        name = uid
                    users[uid] = (userid, name, int(binascii.hexlify(role), 16), password)
                    userdata = userdata[72:]
            return users
        except:
            print("=======exception==============")
            return False

    @api.model
    def cron_download(self):
        machines = self.env['zk.machine'].search([])
        temp = 0
        for machine in machines :
            temp = 1
            _logger.info("******machine exception start***********")
            try:
                _logger.info("***150**try*zk machine************ %s",machine.name)
                machine.download_attendance()
            except Exception as e:
                try:
                    _logger.info("***155**try*zk machine************ %s",machine.name)
                    machine.download_attendance()
                except Exception as e:
                    _logger.info("***157***Exception************ %s",e)
                    continue
                _logger.info("***159***Exception************ %s",e)
                continue
            _logger.info("******machine exception end***********")

    def download_attendance(self):
        zk_attendance = self.env['zk.machine.attendance']
        att_obj = self.env['hr.attendance']
        attendance_conf_id = self.env['zk.correction.conf'].search([], limit = 1)

        for info in self:
            machine_ip = info.name
            port = info.port_no
            zk = zklib.ZKLib(machine_ip, port)
            if info.connection_type == 'connection_2':
                conn = self.device_connect(zk)
            else:
                conn = zk.connect()
            # _logger.info("******connection************ %s",conn)
            if conn:
                zk.enableDevice()
                # serial_number = zk.serialNumber()
                # _logger.info("***************serial_number****** %s",serial_number)
                # zk_version = zk.version()
                # _logger.info("***************zk_version****** %s",zk_version)
                # zk_platform = zk.platform()
                # _logger.info("***************zk_platform****** %s",zk_platform)
                # zk_fmVersion = zk.fmVersion()
                # _logger.info("***************zk_fmVersion****** %s",zk_fmVersion)
                # zk_workCode = zk.workCode()
                # _logger.info("***************zk_workCode****** %s",zk_workCode)
                zk_osversion = zk.osversion()
                _logger.info("***************zk_osversion****** %s",zk_osversion)
                zk_ssr = zk.ssr()
                _logger.info("***************zk_ssr****** %s",zk_ssr)
                zk_deviceName = zk.deviceName()
                _logger.info("***************zk_deviceName****** %s",zk_deviceName)

                user = self.zkgetuser(zk)
                # attendance_custom = zk.getAttendance()
                # _logger.info("**********attendance_custom********* %s",attendance_custom)
                command = CMD_ATTLOG_RRQ
                command_string = ''
                chksum = 0
                session_id = zk.session_id
                reply_id = unpack('HHHH', zk.data_recv[:8])[3]
                buf = zk.createHeader(command, chksum, session_id,
                                      reply_id, command_string)
                zk.zkclient.sendto(buf, zk.address)
                # _logger.info("******session_id************* %s",session_id)
                # _logger.info("******reply_id************* %s",reply_id)
                # _logger.info("******buf************* %s",buf)
                attendance = False
                try:
                    # _logger.info("******193************* %s",zk.attendancedata)
                    zk.data_recv, addr = zk.zkclient.recvfrom(1024)
                    command = unpack('HHHH', zk.data_recv[:8])[0]
                    # _logger.info("******196*******command****** %s",command)

                    if command == CMD_PREPARE_DATA:
                        size = unpack('I', zk.data_recv[8:12])[0]
                        zk_size = size
                    else:
                        zk_size = False
                    # _logger.info("******203*******zk_size****** %s",zk_size)
                    if zk_size:
                        bytes = zk_size
                        while bytes > 0:
                            try:
                                data_recv, addr = zk.zkclient.recvfrom(1032)
                                zk.attendancedata.append(data_recv)
                            except Exception as e:
                                _logger.info("***211**exception*********** %s",e)
                                break
                            bytes -= 1024
                            # _logger.info("***211**bytes*********** %s",bytes)
                        zk.session_id = unpack('HHHH', zk.data_recv[:8])[2]
                        # _logger.info("***212***********")
                        try:
                            data_recv = zk.zkclient.recvfrom(8)
                        except Exception as e:
                            _logger.info("***219**exception*********** %s",e)
                        # _logger.info("***220***********")
                    attendance = []
                    # _logger.info("******205************* %s",zk.attendancedata)
                    if len(zk.attendancedata) > 0:
                        # _logger.info("************224*****")
                        # The first 4 bytes don't seem to be related to the user
                        for x in range(len(zk.attendancedata)):
                            if x > 0:
                                zk.attendancedata[x] = zk.attendancedata[x][8:]
                        attendancedata = b''.join(zk.attendancedata)
                        attendancedata = attendancedata[14:]
                        # _logger.info("************231*****")

                        while len(attendancedata) > 0:
                            try:
                                uid, state, timestamp, space = unpack('24s1s4s11s', attendancedata.ljust(40)[:40])
                                pls = unpack('c', attendancedata[29:30])
                                uid = uid.split(b'\x00', 1)[0].decode('utf-8')
                                tmp = ''
                                # _logger.info("************238*****")
                                for i in reversed(range(int(len(binascii.hexlify(timestamp)) / 2))):
                                    tmp += binascii.hexlify(timestamp).decode('utf-8')[i * 2:(i * 2) + 2]
                                attendance.append((uid, int(binascii.hexlify(state), 16),
                                                   decode_time(int(tmp, 16)), unpack('HHHH', space[:8])[0]))
                                # _logger.info("************243*****")
                                attendancedata = attendancedata[40:]

                            except Exception as e:
                                _logger.info("************248**Exception*** %s",e)
                                break

                except Exception as e:
                    _logger.info("************252**Exception*** %s",e)
                    # attendance = False

                # attendance = [
                #                 ('1', 1, datetime(2020, 1, 19, 11, 54, 15), 0), ('2', 1, datetime(2020, 1, 19, 11, 58, 32), 0), ('3', 1, datetime(2020, 1, 19, 11, 58, 48), 0), ('4', 1, datetime(2020, 1, 19, 12, 0, 8), 0), ('5', 1, datetime(2020, 1, 19, 12, 3, 1), 0), ('6', 1, datetime(2020, 1, 19, 12, 6, 18), 0), ('1', 1, datetime(2020, 1, 19, 14, 43, 13), 0), ('6', 1, datetime(2020, 1, 19, 14, 47, 5), 0), ('13', 1, datetime(2020, 1, 19, 16, 5, 54), 0), ('13', 1, datetime(2020, 1, 19, 16, 6, 3), 1), ('12', 1, datetime(2020, 1, 19, 16, 6, 36), 1), ('9', 1, datetime(2020, 1, 19, 16, 9, 59), 1), ('5', 1, datetime(2020, 1, 19, 16, 11), 1), ('10', 1, datetime(2020, 1, 19, 16, 11, 52), 1), ('7', 1, datetime(2020, 1, 19, 16, 12, 4), 1), ('10', 1, datetime(2020, 1, 19, 16, 13, 40), 1), ('14', 1, datetime(2020, 1, 19, 16, 13, 54), 1), ('1', 1, datetime(2020, 1, 19, 16, 14, 1), 1),
                #                 ('14', 1, datetime(2020, 2, 7, 6, 43, 22), 1), ('14', 1, datetime(2020, 2, 7, 6, 43, 43), 0), ('18', 1, datetime(2020, 2, 7, 6, 43, 48), 0), ('9', 1, datetime(2020, 2, 7, 6, 43, 54), 0), ('16', 1, datetime(2020, 2, 7, 6, 44, 7), 0), ('7', 1, datetime(2020, 2, 7, 6, 44, 19), 0), ('12', 1, datetime(2020, 2, 7, 6, 44, 24), 0), ('11', 1, datetime(2020, 2, 7, 6, 44, 37), 0), ('10', 1, datetime(2020, 2, 7, 6, 46, 9), 0), ('8', 1, datetime(2020, 2, 7, 6, 48, 17), 0), ('17', 1, datetime(2020, 2, 7, 6, 48, 22), 0), ('13', 1, datetime(2020, 2, 7, 6, 50, 22), 0), ('6', 1, datetime(2020, 2, 7, 6, 51, 2), 0), ('14', 1, datetime(2020, 2, 7, 17, 45, 2), 0),  ('6', 1, datetime(2020, 2, 7, 17, 45, 17), 1), ('8', 1, datetime(2020, 2, 7, 17, 48, 58), 1), ('17', 1, datetime(2020, 2, 7, 17, 51, 21), 1), ('7', 1, datetime(2020, 2, 7, 17, 51, 28), 1), ('13', 1, datetime(2020, 2, 7, 17, 51, 30), 1), ('11', 1, datetime(2020, 2, 7, 17, 51, 47), 1), ('9', 1, datetime(2020, 2, 7, 17, 54, 9), 1), ('16', 1, datetime(2020, 2, 7, 17, 54, 32), 1), ('18', 1, datetime(2020, 2, 7, 17, 54, 40), 1), ('12', 1, datetime(2020, 2, 7, 17, 55, 11), 1), ('10', 1, datetime(2020, 2, 7, 17, 55, 21), 1),

                #                 ('6', 1, datetime(2020, 2, 18, 6, 42, 5), 1), ('6', 1, datetime(2020, 2, 18, 6, 42, 17), 0), ('12', 1, datetime(2020, 2, 18, 6, 42, 23), 0), ('7', 1, datetime(2020, 2, 18, 6, 42, 34), 0), ('18', 1, datetime(2020, 2, 18, 6, 42, 59), 0), ('9', 1, datetime(2020, 2, 18, 6, 43, 5), 0), ('16', 1, datetime(2020, 2, 18, 6, 43, 12), 0), ('17', 1, datetime(2020, 2, 18, 6, 47, 33), 0), ('14', 1, datetime(2020, 2, 18, 6, 47, 38), 0), ('8', 1, datetime(2020, 2, 18, 6, 47, 44), 0), ('13', 1, datetime(2020, 2, 18, 6, 50, 35), 0), ('2', 1, datetime(2020, 2, 18, 8, 46, 23), 0), ('18', 1, datetime(2020, 2, 18, 15, 59, 22), 0), ('18', 1, datetime(2020, 2, 18, 15, 59, 34), 1), ('12', 1, datetime(2020, 2, 18, 15, 59, 43), 1), ('8', 1, datetime(2020, 2, 18, 15, 59, 52), 1), ('13', 1, datetime(2020, 2, 18, 16, 2, 59), 1), ('7', 1, datetime(2020, 2, 18, 16, 6, 12), 1), ('16', 1, datetime(2020, 2, 18, 16, 9, 40), 1), ('17', 1, datetime(2020, 2, 18, 16, 11, 21), 1), ('6', 1, datetime(2020, 2, 18, 16, 11, 28), 1), ('14', 1, datetime(2020, 2, 18, 16, 11, 48), 1), ('2', 1, datetime(2020, 2, 18, 18, 0, 49), 1),


                #                 ('7', 1, datetime(2020, 2, 19, 6, 47, 31), 0), ('14', 1, datetime(2020, 2, 19, 6, 47, 46), 0), ('9', 1, datetime(2020, 2, 19, 6, 47, 57), 0), ('18', 1, datetime(2020, 2, 19, 6, 48, 3), 0), ('6', 1, datetime(2020, 2, 19, 6, 48, 12), 0), ('16', 1, datetime(2020, 2, 19, 6, 48, 16), 0), ('10', 1, datetime(2020, 2, 19, 6, 51, 12), 0), ('17', 1, datetime(2020, 2, 19, 6, 53, 4), 0), ('11', 1, datetime(2020, 2, 19, 6, 53, 21), 0), ('8', 1, datetime(2020, 2, 19, 6, 56, 14), 0), ('2', 1, datetime(2020, 2, 19, 8, 49, 24), 0), ('11', 1, datetime(2020, 2, 19, 16, 45, 34), 1), ('13', 1, datetime(2020, 2, 19, 16, 46, 56), 1), ('18', 1, datetime(2020, 2, 19, 16, 48, 48), 1), ('8', 1, datetime(2020, 2, 19, 16, 48, 53), 1), ('16', 1, datetime(2020, 2, 19, 16, 50, 9), 1), ('17', 1, datetime(2020, 2, 19, 16, 50, 43), 1), ('14', 1, datetime(2020, 2, 19, 16, 50, 52), 1), ('7', 1, datetime(2020, 2, 19, 16, 51, 33), 1), ('10', 1, datetime(2020, 2, 19, 16, 52, 10), 1), ('9', 1, datetime(2020, 2, 19, 16, 55, 30), 1), ('6', 1, datetime(2020, 2, 19, 16, 55, 45), 1), ('2', 1, datetime(2020, 2, 19, 18, 2, 21), 1),


                #                 ('14', 1, datetime(2020, 2, 24, 6, 40, 54), 1), ('16', 1, datetime(2020, 2, 24, 6, 41, 3), 1), ('6', 1, datetime(2020, 2, 24, 6, 41, 11), 0), ('14', 1, datetime(2020, 2, 24, 6, 41, 17), 0), ('16', 1, datetime(2020, 2, 24, 6, 41, 24), 0), ('10', 1, datetime(2020, 2, 24, 6, 43, 20), 0), ('17', 1, datetime(2020, 2, 24, 6, 45, 49), 0), ('8', 1, datetime(2020, 2, 24, 6, 46, 3), 0), ('11', 1, datetime(2020, 2, 24, 6, 46, 10), 0), ('13', 1, datetime(2020, 2, 24, 6, 58, 43), 0), ('1', 1, datetime(2020, 2, 24, 7, 42, 43), 0), ('2', 1, datetime(2020, 2, 24, 8, 51, 52), 0), ('14', 1, datetime(2020, 2, 24, 16, 29, 4), 0), ('11', 1, datetime(2020, 2, 24, 16, 32, 30), 1), ('17', 1, datetime(2020, 2, 24, 16, 34, 27), 1), ('8', 1, datetime(2020, 2, 24, 16, 34, 56), 1), ('13', 1, datetime(2020, 2, 24, 16, 35, 14), 1), ('6', 1, datetime(2020, 2, 24, 16, 36, 1), 1), ('10', 1, datetime(2020, 2, 24, 16, 36, 49), 1), ('16', 1, datetime(2020, 2, 24, 16, 38, 13), 1), ('2', 1, datetime(2020, 2, 24, 18, 2, 35), 1), ('6', 1, datetime(2020, 2, 25, 6, 46, 17), 0), ('12', 1, datetime(2020, 2, 25, 6, 46, 24), 0), ('16', 1, datetime(2020, 2, 25, 6, 46, 41), 0), ('9', 1, datetime(2020, 2, 25, 6, 48, 49), 0), ('10', 1, datetime(2020, 2, 25, 6, 49, 1), 0), ('8', 1, datetime(2020, 2, 25, 6, 52, 13), 0), ('17', 1, datetime(2020, 2, 25, 6, 52, 26), 0), ('2', 1, datetime(2020, 2, 25, 8, 51, 5), 0), ('12', 1, datetime(2020, 2, 25, 16, 51, 57), 1), ('8', 1, datetime(2020, 2, 25, 16, 52, 18), 1), ('9', 1, datetime(2020, 2, 25, 16, 55, 40), 1), ('6', 1, datetime(2020, 2, 25, 16, 55, 45), 1), ('14', 1, datetime(2020, 2, 25, 16, 55, 51), 1), ('16', 1, datetime(2020, 2, 25, 16, 56, 7), 1), ('17', 1, datetime(2020, 2, 25, 16, 56, 55), 1), ('10', 1, datetime(2020, 2, 25, 17, 0, 23), 1), ('2', 1, datetime(2020, 2, 25, 18, 1, 20), 1)]

                # _logger.info("========user====== %s", len(user))
                if attendance:

                    _logger.info("========attendance====== %s", len(attendance))

                else:
                    _logger.info("========attendance====== %s", attendance)
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
                        atten_start_time = atten_time.replace(minute=00, hour=00, second=00)
                        atten_end_time = atten_time.replace(minute=59, hour=23, second=59)
                        att_update_min = atten_time - timedelta(minutes=1)
                        atten_time = fields.Datetime.to_string(atten_time)
                        #user = {1: ('1', 'Amjidzareen', 0, ''), 2: ('2', 'Faizal', 0, ''), 3: ('3', 'Sathuram', 0, ''), 4: ('4', 'Saleem', 0, ''), 5: ('5', 'Nilo', 0, ''), 6: ('6', 'Abdul', 0, ''), 7: ('7', 'Prakash', 0, ''), 8: ('8', 'Ram', 0, ''), 9: ('9', 'Victoria', 0, ''), 10: ('1', 'David', 0, ''), 11: ('11', 'Indika', 0, ''), 12: ('12', 'Mahindra', 0, ''), 13: ('13', 'Sohail', 0, ''), 14: ('14', 'Smart', 0, ''), 15: ('15', 'Sathyamoorthy', 0, ''), 16: ('16', 'Saeed', 0, ''), 17: ('17', 'Shyam', 0, ''), 18: ('18', 'Jamshid', 0, ''), 19: ('19', 'Mohammad', 0, ''), 20: ('2', 'Ryan', 0, ''), 21: ('21', 'Daniel', 0, ''), 22: ('22', 'Jaffer', 0, '')}
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
                                            try:
                                                zk_attendance.create({'employee_id': get_user_id.id,
                                                                      'device_id': each[0],
                                                                      'attendance_type': str(each[1]),
                                                                      'punch_type': str(each[3]),
                                                                      'punching_time': atten_time,
                                                                      'address_id': info.address_id.id})

                                                #split Global check-in and check-out time
                                                time_in = attendance_conf_id.global_in_time.split(':')
                                                time_out = attendance_conf_id.global_out_time.split(':')
                                                if each[3] == 0: #check-in
                                                    att_var = att_obj.search([('employee_id', '=', get_user_id.id),
                                                                           ('check_out', '=', False), ('check_in', '<', atten_start_time)], order='check_in desc', limit=1)
                                                    att_var_for_same_day = att_obj.search([('employee_id', '=', get_user_id.id),
                                                                           ('check_in', '>=', atten_start_time),('check_in', '<=', atten_end_time)], order='check_in desc', limit=1)

                                                    att_in_list = zk_attendance.search([('employee_id', '=', get_user_id.id),
                                                                          ('punching_time', '>=', atten_start_time),('punching_time', '<=', atten_end_time),('punch_type', '=', '0')])
                                                    if not att_var:
                                                        #if no check-out time before today, check-in not on same day and there is multiple check-in on same da then tale letest punch time in check-in.
                                                        if not att_var_for_same_day:
                                                            if len(att_in_list) == 1:
                                                                att_obj.create({'employee_id': get_user_id.id,
                                                                                'check_in': atten_time})

                                                            else:
                                                                oldest_in_time = att_in_list[0].punching_time
                                                                n = len(att_in_list)
                                                                for l in range(1, n):
                                                                    if oldest_in_time > att_in_list[l].punching_time:
                                                                        oldest_in_time = att_in_list[l].punching_time
                                                                if str(oldest_in_time) > atten_time:
                                                                    hr_att = att_obj.search([('employee_id', '=', get_user_id.id),
                                                                            ('check_in', '>=', atten_start_time),('check_in', '<=', atten_end_time)], limit=1)
                                                                    hr_att.write({'check_in': atten_time})
                                                                else:
                                                                    hr_att = att_obj.search([('employee_id', '=', get_user_id.id),
                                                                            ('check_in', '>=', atten_start_time),('check_in', '<=', atten_end_time)], limit=1)
                                                                    hr_att.write({'check_in': oldest_in_time})
                                                    else:
                                                        # if not check-out and check-in on next date.
                                                        if len(att_var) == 1:
                                                            check_in_date = att_var.check_in
                                                            check_out = check_in_date.replace(minute=int(time_out[1]), hour=int(time_out[0]), second=00)
                                                            att_var.write({'check_out': check_out})
                                                            att_obj.create({'employee_id': get_user_id.id,
                                                                            'check_in': atten_time})

                                                        else:
                                                            check_in_date = att_var[-1].check_in
                                                            check_out = check_in_date.replace(minute=int(time_out[1]), hour=int(time_out[0]), second=00)
                                                            att_var[-1].write({'check_out': check_out})
                                                            att_obj.create({'employee_id': get_user_id.id,
                                                                            'check_in': atten_time})

                                                if each[3] == 1: #check-out
                                                    att_in_list = zk_attendance.search([('employee_id', '=', get_user_id.id),
                                                                          ('punching_time', '>=', atten_start_time),('punching_time', '<=', atten_end_time),('punch_type', '=', '1')])

                                                    if len(att_in_list) == 1:
                                                        # if check-out first time
                                                        hr_att = att_obj.search([('employee_id', '=', get_user_id.id),
                                                                          ('check_in', '>=', atten_start_time),('check_in', '<=', atten_end_time)], limit=1)
                                                        if not hr_att:
                                                            # check-out without check-in on same day.
                                                            in_time = atten_start_time.replace(minute=int(time_in[1]), hour=int(time_in[0]), second=00)
                                                            if str(in_time) < str(atten_time):
                                                                #check-out time is greater than check-in time
                                                                att_var = att_obj.search([('employee_id', '=', get_user_id.id),
                                                                           ('check_out', '=', False), ('check_in', '<', atten_start_time)], order='check_in desc', limit=1)
                                                                if not att_var:
                                                                    hr_att = att_obj.create({'employee_id': get_user_id.id,
                                                                                    'check_in': in_time})
                                                                    hr_att.write({'check_out': atten_time})
                                                                else:
                                                                    check_in_date = att_var.check_in
                                                                    check_out = check_in_date.replace(minute=int(time_out[1]), hour=int(time_out[0]), second=00)
                                                                    att_var.write({'check_out': check_out})
                                                                    hr_att = att_obj.create({'employee_id': get_user_id.id,
                                                                                    'check_in': in_time})
                                                                    hr_att.write({'check_out': atten_time})
                                                            else:
                                                                #check-out time is smaller then check-in time
                                                                att_var = att_obj.search([('employee_id', '=', get_user_id.id),
                                                                           ('check_out', '=', False), ('check_in', '<', atten_start_time)], order='check_in desc', limit=1)
                                                                if not att_var:
                                                                    hr_att_id = att_obj.create({'employee_id': get_user_id.id,'check_in': att_update_min})
                                                                    hr_att_id.write({'check_out': atten_time})
                                                                else:
                                                                    check_in_date = att_var.check_in
                                                                    check_out = check_in_date.replace(minute=int(time_out[1]), hour=int(time_out[0]), second=00)
                                                                    att_var.write({'check_out': check_out})
                                                                    hr_att = att_obj.create({'employee_id': get_user_id.id,
                                                                                    'check_in': att_update_min})
                                                                    hr_att.write({'check_out': atten_time})

                                                        else:
                                                            hr_att.write({'check_out': atten_time})

                                                    else:
                                                        # multiple check-out on same date.
                                                        oldest_in_time = att_in_list[0].punching_time
                                                        n = len(att_in_list)
                                                        for l in range(1, n):
                                                            if att_in_list[l].punching_time > oldest_in_time:
                                                                oldest_in_time = att_in_list[l].punching_time
                                                        if str(oldest_in_time) > str(atten_time):
                                                            in_time = atten_start_time.replace(minute=int(time_in[1]), hour=int(time_in[0]), second=00)
                                                            hr_att = att_obj.search([('employee_id', '=', get_user_id.id),
                                                                            ('check_in', '>=', atten_start_time),('check_in', '<=', atten_end_time)], limit=1)
                                                            if str(in_time) < str(oldest_in_time):
                                                                hr_att.write({'check_out': oldest_in_time})
                                                            else:
                                                                time_min_in = int(time_in[1]) + 1
                                                                d_atten_time = atten_start_time.replace(minute=time_min_in, hour=int(time_in[0]), second=00)
                                                                hr_att.write({'check_out': d_atten_time})
                                                        else:
                                                            in_time = atten_start_time.replace(minute=int(time_in[1]), hour=int(time_in[0]), second=00)
                                                            hr_att = att_obj.search([('employee_id', '=', get_user_id.id),
                                                                        ('check_in', '>=', atten_start_time),('check_in', '<=', atten_end_time)], limit=1)
                                                            if str(atten_time) > str(in_time):
                                                                hr_att.write({'check_out': atten_time})
                                                            else:
                                                                time_min_in = int(time_in[1]) + 1
                                                                d_atten_time = atten_start_time.replace(minute=time_min_in, hour=int(time_in[0]), second=00)
                                                                hr_att.write({'check_out': d_atten_time})

                                            except Exception as e:
                                                _logger.info("******Exception************ %s",e)
                                                continue

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
                                            if each[3] == 0:
                                                att_obj.create({'employee_id': employee.id,
                                                                'check_in': atten_time})
                                            if each[3] == 1:
                                                g_time_in = attendance_conf_id.global_in_time.split(':')
                                                in_time = atten_start_time.replace(minute=int(g_time_in[1]), hour=int(g_time_in[0]), second=00)
                                                att_id  = att_obj.create({'employee_id': employee.id,
                                                                'check_in': in_time})
                                                att_id.write({'check_out': atten_time})
                                        except Exception as e:
                                            _logger.info("++++++++++++Att Exception++++++++++++++++++++++", e)
                                            continue
                                else:
                                    pass
                    zk.enableDevice()
                    #zk.disconnect()
                    return True
                else:
                    raise UserError(_('Unable to get the attendance log, please try again later.'))
            else:
                raise UserError(_('Unable to connect, please check the parameters and network connections.'))
