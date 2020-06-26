# -*- encoding: utf-8 -*-
# Part of Prolitus Technologies Pvt. Ltd. See LICENSE file for full copyright and licensing details.

{
    'name': 'custom_zk_attendance',
    'version': '1.0',
    'category': 'HR Attendance',
    'author': 'Prolitus Technologies Pvt. Ltd.',
    'sequence': 50,
    'summary': 'HR Attendance',
    'depends': ['pro_hr_zk_attendance'],
    'website': 'www.prolitus.com',
    'description': """
         This module helps to fetch Attendance data from server.
    """,
    'data': [
             #'wizard/hr_attendance_wizard_views.xml',
	     'security/ir.model.access.csv',
	     'views/zk_machine_correction_conf.xml',
         'data/attendance_data_correction_cron.xml',
                ],
    'qweb': [],
    'application': True,
    'installable': True,
    'auto_install': False,
}
