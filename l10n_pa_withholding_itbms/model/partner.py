# coding: utf-8

from openerp.addons import decimal_precision as dp
from openerp import models, fields


class ResPartner(models.Model):
    _inherit = 'res.partner'
    wh_agent_itbms = fields.Boolean(
        string='ITBMS Withholding Agent',
        help="Indicate if the Partner is a ITBMS Withholding Agent")
    wh_rate_itbms = fields.Float(
        string='ITBMS Withholding Rate', digits=dp.get_precision('Withhold'),
        default=50.0,
        help="ITBMS Withholding Rate")
