# coding: utf-8

from openerp import models, fields


class ResPartner(models.Model):
    _inherit = 'res.partner'
    wh_agent_itbms = fields.Boolean(
        string='ITBMS Withholding Agent',
        help="Indicate if the Partner is a ITBMS Withholding Agent")
