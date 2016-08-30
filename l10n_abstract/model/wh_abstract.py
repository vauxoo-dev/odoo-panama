# coding: utf-8

import time

from openerp.addons import decimal_precision as dp
from openerp import models, fields, api, exceptions, _


class WhDocumentLineAbstract(models.AbstractModel):
    _name = 'wh.document.line.abstract'
    _description = "Withholding Document Line Abstract"

    inv_tax_id = fields.Many2one(
        'account.invoice.tax', string='Invoice Tax',
        ondelete='set null', help="Tax Line")
    tax_id = fields.Many2one(
        'account.tax', string='Tax',
        related='inv_tax_id.tax_id', store=True, readonly=True,
        ondelete='set null', help="Tax")
    name = fields.Char(
        string='Tax Name', size=256,
        related='inv_tax_id.name', store=True, readonly=True,
        ondelete='set null', help=" Tax Name")
    # /!\ NOTE: `base_tax` used to be `base`
    base_tax = fields.Float(
        string='Tax Base', digits=dp.get_precision('Withhold'),
        help="Tax Base. Untaxed Amount")
    # /!\ NOTE: `base_wh` used to be `amount`
    base_wh = fields.Float(
        string='Withholding Base', digits=dp.get_precision('Withhold'),
        help="Base upon which to Apply Withholding")
    company_id = fields.Many2one(
        'res.company', string='Company',
        related='inv_tax_id.company_id', store=True, readonly=True,
        ondelete='set null', help="Company")
    # /!\ NOTE: `wh_tax` used to be `amount_ret`
    wh_tax = fields.Float(
        string='Withheld Tax', digits=dp.get_precision('Withhold'),
        help="Withholding amount")


class WhDocumentAbstract(models.AbstractModel):
    _name = "wh.document.abstract"
    _description = "Withholding Document Abstract"

    name = fields.Char(
        string='Description', size=64, required=True,
        help="Withholding line Description")
    invoice_id = fields.Many2one(
        'account.invoice', string='Invoice', required=True,
        ondelete='restrict', help="Withholding invoice")
    supplier_invoice_number = fields.Char(
        string='Supplier Invoice Number', size=64,
        related='invoice_id.supplier_invoice_number',
        store=True, readonly=True)
    # /!\ NOTE: `wh_tax` used to be `amount_tax_ret`
    wh_tax = fields.Float(
        string='Withheld Tax', digits=dp.get_precision('Withhold'),
        help="Withheld tax amount")
    base_wh = fields.Float(
        string='Withholding Base', digits=dp.get_precision('Withhold'),
        help="Base upon which to Apply Withholding")
    # /!\ NOTE: `base_tax` used to be `base_ret`
    base_tax = fields.Float(
        string='Tax Base', digits=dp.get_precision('Withhold'),
        help="Tax Base. Untaxed Amount")
    move_id = fields.Many2one(
        'account.move', string='Account Entry', readonly=True,
        ondelete='restrict', help="Account entry")
    # /!\ NOTE: `wh_rate` used to be `wh_iva_rate`
    wh_rate = fields.Float(
        string='Withholding Rate', digits=dp.get_precision('Withhold'),
        help="Withholding Rate")


class WhAbstract(models.AbstractModel):
    _name = "wh.abstract"
    _description = "Withholding Abstract"

    @api.multi
    def name_get(self):
        res = []
        for item in self:
            if item.number and item.state == 'done':
                res.append((item.id, '%s (%s)' % (item.number, item.name)))
            else:
                res.append((item.id, '%s' % (item.name)))
        return res

    @api.model
    def _get_type(self):
        """ Return invoice type
        """
        context = self._context
        return context.get('type', 'in_invoice')

    @api.model
    def _get_wh_code_seq(self):
        """ Return a iva journal depending of invoice type
        """
        raise exceptions.except_orm(
            _('Method to be Deployed'), 'Warning!!!')
        return

    @api.model
    def _get_journal(self):
        """Dummy method to fetch a Journal on real model is to be override"""
        return []

    @api.model
    def _get_fortnight(self):
        """ Return currency to use
        """
        dt = time.strftime('%Y-%m-%d')
        tm_mday = time.strptime(dt, '%Y-%m-%d').tm_mday
        return tm_mday <= 15 and 'False' or 'True'

    @api.model
    def _get_currency(self):
        """ Return currency to use
        """
        if self.env.user.company_id:
            return self.env.user.company_id.currency_id.id
        return self.env['res.currency'].search([('rate', '=', 1.0)], limit=1)

    name = fields.Char(
        string='Description', size=64, readonly=True,
        states={'draft': [('readonly', False)]}, required=True,
        help="Description of withholding")
    code = fields.Char(
        string='Internal Code', size=32, readonly=True,
        states={'draft': [('readonly', False)]}, default=_get_wh_code_seq,
        help="Internal withholding reference")
    number = fields.Char(
        string='Withholding Number', size=32, readonly=True,
        states={'draft': [('readonly', False)]},
        help="Withholding number")
    type = fields.Selection([
        ('out_invoice', 'Customer Invoice'),
        ('in_invoice', 'Supplier Invoice'),
        ], string='Type', readonly=True, default=_get_type,
        help="Withholding type")
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('done', 'Done'),
        ('cancel', 'Cancelled')
        ], string='State', readonly=True, default='draft',
        help="Withholding State")
    # /!\ NOTE: `date_accounting` used to be `date_ret`
    date_accounting = fields.Date(
        string='Accounting Date', readonly=True,
        states={'draft': [('readonly', False)]},
        help="Keep empty to use the current date")
    date = fields.Date(
        string='Document Date', readonly=True,
        states={'draft': [('readonly', False)]},
        help="Emission//Document Date")
    account_id = fields.Many2one(
        'account.account', string='Account', required=True, readonly=True,
        states={'draft': [('readonly', False)]},
        help="The pay account used for this withholding.")
    currency_id = fields.Many2one(
        'res.currency', string='Currency', required=True, readonly=True,
        states={'draft': [('readonly', False)]}, default=_get_currency,
        help="Currency")
    period_id = fields.Many2one(
        'account.period', string='Force Period', readonly=True,
        domain=[('state', '<>', 'done')],
        states={'draft': [('readonly', False)]},
        help="Keep empty to use the period of the validation(Withholding"
             " date) date.")
    company_id = fields.Many2one(
        'res.company', string='Company', required=True, readonly=True,
        default=lambda self: self.env.user.company_id.id,
        help="Company")
    partner_id = fields.Many2one(
        'res.partner', string='Partner', readonly=True, required=True,
        states={'draft': [('readonly', False)]},
        help="Withholding customer/supplier")
    journal_id = fields.Many2one(
        'account.journal', string='Journal', required=True, readonly=True,
        states={'draft': [('readonly', False)]}, default=_get_journal,
        help="Journal entry")
    # /!\ NOTE: `base_tax` used to be `amount_base_ret`
    base_tax = fields.Float(
        string='Total Tax Base', digits=dp.get_precision('Withhold'),
        help="Total Tax Base. Total Untaxed Amount")
    # /!\ NOTE: `wh_tax` used to be `total_tax_ret`
    wh_tax = fields.Float(
        string='Total Withheld Tax', digits=dp.get_precision('Withhold'),
        help="Withheld Tax Amount")
    fortnight = fields.Selection([
        ('False', "First Fortnight"),
        ('True', "Second Fortnight")
        ], string="Fortnight", readonly=True,
        states={"draft": [("readonly", False)]}, default=_get_fortnight,
        help="Withholding type")
    third_party_id = fields.Many2one(
        'res.partner', string='Third Party Partner',
        help='Third Party Partner')
