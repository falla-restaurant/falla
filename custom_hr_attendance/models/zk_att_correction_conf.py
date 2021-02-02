
import pytz
import sys
import datetime
#from datetime import datetime
import logging
import binascii
from odoo import api, fields, models
from odoo import _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class ZkCorrectionConf(models.Model):
    _name = 'zk.correction.conf'
    _rec_name = 'id'

    #add_remove_hours = fields.Integer(string='Add Time', default='9', required=True)
    global_in_time = fields.Char(string='Global check-in time', default='09:30', required=True)
    global_out_time = fields.Char(string='Global check-out time', default='18:30', required=True)

    @api.model
    def attendance_data_correction_cron(self):
        attendance_conf_id = self.env['zk.correction.conf'].search([], limit = 1)
        
        if attendance_conf_id:
            time_out = attendance_conf_id.global_out_time.split(':')
            ir_cron_list = self.env['ir.cron'].search([('name', '=', 'Attendance Data Correction')], limit=1)
            cron_run_date = ir_cron_list.nextcall
            month_first_date = cron_run_date.replace(day=1)
            previous_month_last_date = month_first_date - datetime.timedelta(days=1)
            previous_month_first_date = previous_month_last_date.replace(day=1)
            previous_month_first_date = previous_month_first_date.replace(minute=00, hour=00, second=00)
            previous_month_last_date = previous_month_last_date.replace(minute=59, hour=23, second=59)
            attendance_list = self.env['hr.attendance'].search([('create_date', '>=', str(previous_month_first_date)), ('write_date', '<=', str(previous_month_last_date)), ('check_out', '=', False)])
            for attendance in attendance_list:
                check_in_date = attendance.check_in
                check_out = check_in_date.replace(minute=int(time_out[1]), hour=int(time_out[0]), second=00)
                attendance.check_out = check_out
        else:
            raise UserError(_('Please configure global check-in and check-out time.'))