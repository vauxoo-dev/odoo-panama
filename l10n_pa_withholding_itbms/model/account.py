# coding: utf-8

from openerp import models, fields


class AccountTax(models.Model):
    _inherit = 'account.tax'

    wh = fields.Boolean(
        string='Withholdable',
        help="Indicate if the tax must be withheld")
    wh_itbms_collected_account_id = fields.Many2one(
        'account.account',
        string="Invoice ITBMS Withholding Account",
        domain="[('type', '=', 'other')]",
        help="This account will be used when applying a withhold to an"
        " Invoice")
    wh_itbms_paid_account_id = fields.Many2one(
        'account.account',
        string="Refund ITBMS Withholding Account",
        domain="[('type', '=', 'other')]",
        help="This account will be used when applying a withhold to a"
        " Refund")
