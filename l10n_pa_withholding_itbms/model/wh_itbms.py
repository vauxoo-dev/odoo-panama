# coding: utf-8

import time

from openerp.addons import decimal_precision as dp
from openerp import models, fields, api, exceptions, _


class WhDocumentLineItbms(models.Model):
    _name = 'wh.document.line.itbms'
    _inherit = ['wh.document.line.abstract']
    _description = "Withholding Document Line ITBMS"

    @api.multi
    @api.depends('inv_tax_id')
    def _get_base_amount(self):
        """ Return withholding amount
        """
        for record in self:
            exc = self.env['wh.itbms'].exc(
                record.inv_tax_id.invoice_id.currency_id.id,
                record.inv_tax_id.invoice_id.company_id.currency_id.id,
                record.wh_document_id.withholding_id.date)
            record.base_tax = exc(record.inv_tax_id.base_tax)
            record.base_wh = exc(record.inv_tax_id.amount)

    @api.multi
    def _set_wh_tax(self):
        """ Change withholding amount into itbms line
        @param value: new value for retention amount
        """
        for record in self:
            if record.wh_document_id.withholding_id.type != 'out_invoice':
                continue
            if not record.wh_tax:
                continue
            sql_str = """UPDATE wh_document_line_itbms
                    SET wh_tax='%s'
                    WHERE id=%d """ % (record.wh_tax, record.id)
            self._cr.execute(sql_str)
        return True

    @api.multi
    @api.depends('base_wh', 'wh_document_id.wh_rate')
    def _get_wh_tax(self):
        """ Return withholding amount
        """
        for record in self:
            # TODO: THIS NEEDS REFACTORY IN ORDER TO COMPLY WITH THE SALE
            # WITHHOLDING
            record.wh_tax = round(
                (record.base_wh * record.wh_document_id.wh_rate / 100.0) +
                0.00000001, 2)

    wh_document_id = fields.Many2one(
        'wh.document.itbms', string='ITBMS Withholding Line', required=True,
        ondelete='cascade', help="ITBMS Withholding Line")
    name = fields.Char(
        string='Tax Name', size=256,
        related='inv_tax_id.name', store=True, readonly=True,
        ondelete='set null', help=" Tax Name")
    inv_tax_id = fields.Many2one(
        'account.invoice.tax', string='Invoice Tax',
        ondelete='set null', help="Tax Line")
    tax_id = fields.Many2one(
        'account.tax', string='Tax',
        related='inv_tax_id.tax_id', store=True, readonly=True,
        ondelete='set null', help="Tax")
    company_id = fields.Many2one(
        'res.company', string='Company',
        related='inv_tax_id.company_id', store=True, readonly=True,
        ondelete='set null', help="Company")
    # /!\ NOTE: `base_tax` used to be `base`
    base_tax = fields.Float(
        string='Tax Base', digits=dp.get_precision('Withhold'),
        store=True, compute=_get_base_amount,
        help="Tax Base. Untaxed Amount")
    # /!\ NOTE: `base_wh` used to be `amount`
    base_wh = fields.Float(
        string='Withholding Base', digits=dp.get_precision('Withhold'),
        store=True, compute=_get_base_amount,
        help="Base upon which to Apply Withholding")
    # /!\ NOTE: `wh_tax` used to be `amount_ret`
    wh_tax = fields.Float(
        string='Withheld Tax', digits=dp.get_precision('Withhold'),
        store=True, compute=_get_wh_tax, inverse=_set_wh_tax,
        help="Withholding amount")


class WhDocumentItbms(models.Model):
    _name = 'wh.document.itbms'
    _inherit = ['wh.document.abstract']
    _description = "Withholding Document ITBMS"

    @api.multi
    def load_taxes(self):
        """ Clean and load again tax lines of the withholding voucher
        """
        awilt = self.env['wh.document.line.itbms']
        partner = self.env['res.partner']

        for rec in self:
            if rec.invoice_id:
                company_partner_id = rec.invoice_id.company_id.partner_id
                rate = rec.withholding_id.type == 'out_invoice' and \
                    partner._find_accounting_partner(
                        company_partner_id).wh_rate_itbms or \
                    partner._find_accounting_partner(
                        rec.invoice_id.partner_id).wh_rate_itbms
                rec.write({'wh_rate': rate})
                # Clean tax lines of the withholding voucher
                awilt.search([('wh_document_id', '=', rec.id)]).unlink()
                # Filter withholdable taxes
                for tax in rec.invoice_id.tax_line.filtered("tax_id.wh"):
                    # Load again tax lines of the withholding voucher
                    awilt.create({'wh_document_id': rec.id,
                                  'inv_tax_id': tax.id,
                                  'tax_id': tax.tax_id.id})
        return True

    @api.multi
    @api.depends('tax_line.wh_tax', 'tax_line.base_tax')
    def _amount_all(self):
        """ Return amount total each line
        """
        for rec in self:
            if rec.invoice_id:
                if rec.invoice_id.type not in ('in_refund',):
                    rec.wh_tax = sum(l.wh_tax for l in rec.tax_line)
                    rec.base_tax = sum(l.base_tax for l in rec.tax_line)
                else:
                    rec.wh_tax = -sum(l.wh_tax for l in rec.tax_line)
                    rec.base_tax = -sum(l.base_tax for l in rec.tax_line)
            else:
                rec.wh_tax = 0
                rec.base_tax = 0

    # /!\ NOTE: `withholding_id` used to be `retention_id`
    withholding_id = fields.Many2one(
        'wh.itbms', string='ITBMS Withholding',
        ondelete='cascade', help="ITBMS Withholding")
    move_id = fields.Many2one(
        'account.move', string='Account Entry', readonly=True,
        ondelete='restrict', help="Account entry")
    invoice_id = fields.Many2one(
        'account.invoice', string='Invoice', required=True,
        ondelete='restrict', help="Withholding invoice")
    supplier_invoice_number = fields.Char(
        string='Supplier Invoice Number', size=64,
        related='invoice_id.supplier_invoice_number',
        store=True, readonly=True)
    tax_line = fields.One2many(
        'wh.document.line.itbms', 'wh_document_id', string='Taxes',
        help="Invoice taxes")
    date = fields.Date(
        string='Voucher Date',
        related='withholding_id.date',
        help='Emission/Voucher/Document date')
    # /!\ NOTE: `date_accounting` used to be `date_ret`
    date_accounting = fields.Date(
        string='Accounting Date',
        related='withholding_id.date_accounting',
        help='Accouting date. Date Withholding')
    # /!\ NOTE: `wh_tax` used to be `amount_tax_ret`
    wh_tax = fields.Float(
        string='Withheld Tax', digits=dp.get_precision('Withhold'),
        compute=_amount_all,
        help="Withheld tax amount")
    # /!\ NOTE: `base_tax` used to be `base_ret`
    base_tax = fields.Float(
        string='Tax Base', digits=dp.get_precision('Withhold'),
        compute=_amount_all,
        help="Tax Base. Untaxed Amount")

    _sql_constraints = [
        ('ret_fact_uniq', 'unique (invoice_id)', 'The invoice has already'
         ' assigned in withholding, you cannot assigned it twice!')
    ]

    @api.multi
    def invoice_id_change(self, invoice_id):
        """ Return invoice data to assign to withholding
        @param invoice: invoice for assign a withholding
        """
        result = {}
        if invoice_id:
            invoice = self.env['account.invoice'].browse(invoice_id)
            self._cr.execute('SELECT withholding_id '
                             'FROM wh_document_itbms '
                             'WHERE invoice_id=%s' % (invoice_id))
            ret_ids = self._cr.fetchone()
            if bool(ret_ids):
                ret = self.env['wh.itbms'].browse(ret_ids[0])
                raise exceptions.except_orm(
                    'Assigned Invoice !',
                    "The invoice has already assigned in withholding"
                    " code: '%s' !" % (ret.code))
            result.update({
                'name': invoice.name,
                'supplier_invoice_number': invoice.supplier_invoice_number})

        return {'value': result}


class WhItbms(models.Model):
    _name = 'wh.itbms'
    _inherit = ['wh.abstract']
    _description = "Withholding ITBMS"

    @api.multi
    def name_get(self):
        res = []
        for item in self:
            if item.number and item.state == 'done':
                res.append((item.id, '%s (%s)' % (item.number, item.name)))
            else:
                res.append((item.id, '%s' % (item.name)))
        return res

    @api.multi
    @api.depends('wh_lines.wh_tax', 'wh_lines.base_tax')
    def _wh_tax_all(self):
        """ Return withholding amount total each line
        """
        for rec in self:
            rec.total_tax_ret = sum(l.wh_tax for l in rec.wh_lines)
            rec.amount_base_tax = sum(l.base_tax for l in rec.wh_lines)

    @api.model
    def _get_wh_itbms_seq(self):
        """ Generate sequences for records of withholding itbms
        """
        self._cr.execute(
            "select id,number_next,number_increment,prefix,suffix,padding "
            "from ir_sequence "
            "where code='wh.itbms' and active=True")
        res = self._cr.dictfetchone()
        if res:
            sequence = self.env['ir.sequence'].browse(res['id'])
            if res['number_next']:
                return sequence._next()
            else:
                return sequence._process(res['prefix']) + \
                    sequence._process(res['suffix'])
        return False

    @api.model
    def _get_type(self):
        """ Return invoice type
        """
        context = self._context
        return context.get('type', 'in_invoice')

    @api.model
    def _get_journal(self):
        """ Return a itbms journal depending of invoice type
        """
        context = self._context
        type_inv = context.get('type', 'in_invoice')
        type2journal = {'out_invoice': 'iva_sale',
                        'in_invoice': 'iva_purchase'}
        domain = [('type', '=', type2journal.get(type_inv, 'iva_purchase'))]
        return self.env['account.journal'].search(domain, limit=1)

    @api.model
    def _get_wh_code_seq(self):
        """ Return a Sequence for code in ITBMS"""
        return None

    @api.model
    def _get_currency(self):
        """ Return currency to use
        """
        if self.env.user.company_id:
            return self.env.user.company_id.currency_id.id
        return self.env['res.currency'].search([('rate', '=', 1.0)], limit=1)

    @api.multi
    @api.depends('wh_lines.wh_tax', 'wh_lines.base_tax')
    def _amount_ret_all(self):
        """ Return withholding amount total each line
        """
        for rec in self:
            rec.wh_tax = sum(l.wh_tax for l in rec.wh_lines)
            rec.base_tax = sum(l.base_tax for l in rec.wh_lines)

    wh_lines = fields.One2many(
        'wh.document.itbms', 'withholding_id',
        string='ITBMS Withholding lines', readonly=True,
        states={'draft': [('readonly', False)]},
        help="ITBMS Withholding lines")
    consolidate_itbms_wh = fields.Boolean(
        string='Fortnight Consolidate Wh. ITBMS',
        help='If set then the withholdings ITBMS generate in a same'
        ' fortnight will be grouped in one withholding receipt.')
    code = fields.Char(
        string='Internal Code', size=32, readonly=True,
        states={'draft': [('readonly', False)]}, default=_get_wh_code_seq,
        help="Internal withholding reference")
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
    third_party_id = fields.Many2one(
        'res.partner', string='Third Party Partner',
        help='Third Party Partner')
    # /!\ NOTE: `base_tax` used to be `amount_base_ret`
    base_tax = fields.Float(
        string='Total Tax Base', digits=dp.get_precision('Withhold'),
        compute='_amount_ret_all',
        help="Total Tax Base. Total Untaxed Amount")
    # /!\ NOTE: `wh_tax` used to be `total_tax_ret`
    wh_tax = fields.Float(
        string='Total Withheld Tax', digits=dp.get_precision('Withhold'),
        compute='_amount_ret_all',
        help="Withheld Tax Amount")

    @api.multi
    def action_cancel(self):
        """ Call cancel_move and return True
        """
        self.cancel_move()
        self.clear_wh_lines()
        return True

    @api.multi
    def cancel_move(self):
        """ Delete move lines related with withholding and cancel
        """
        moves = []
        for ret in self:
            if ret.state == 'done':
                for ret_line in ret.wh_lines:
                    moves.append(ret_line.move_id)
                    # first, detach the move id
                    ret_line.write({'move_id': False})
            # second, set the withholding as cancelled
            ret.write({'state': 'cancel'})
        if moves:
            for move in moves:
                # third, invalidate the move(s)
                move.button_cancel()
                # last, delete the move(s)
                move.unlink()
        return True

    @api.multi
    def action_cancel_draft(self):
        """Restarting the workflow withholding vat.
        The state is placed in draft.
        """
        self.write({'state': 'draft'})
        self.delete_workflow()
        self.create_workflow()
        return True

    @api.model
    def _get_valid_wh(self, wh_tax, amount, wh_rate,
                      offset=0.5):
        """ This method can be override in a way that
        you can afford your own value for the offset
        @param wh_tax: withholding amount
        @param amount: invoice amount
        @param wh_rate: itbms rate
        @param offset: compensation
        """

        return (wh_tax >= amount * (wh_rate - offset) / 100.0 and
                wh_tax <= amount * (wh_rate + offset) / 100.0)

    @api.multi
    def check_wh_taxes(self):
        """ Check that are valid and that amount retention is not greater than amount
        """
        note = _('Taxes in the following invoices have been miscalculated\n\n')
        error_msg = ''
        for record in self:
            wh_line_ids = []
            for wh_line in record.wh_lines:
                for tax in wh_line.tax_line:
                    if not record._get_valid_wh(
                            tax.wh_tax, tax.base_wh,
                            tax.wh_document_id.wh_rate):
                        if wh_line.id not in wh_line_ids:
                            note += _('\tInvoice: %s, %s, %s\n') % (
                                wh_line.invoice_id.name,
                                wh_line.invoice_id.number,
                                wh_line.invoice_id.supplier_invoice_number or
                                '/')
                            wh_line_ids.append(wh_line.id)
                        note += '\t\t%s\n' % tax.name
                    if tax.wh_tax > tax.base_wh:
                        porcent = '%'
                        error_msg += _(
                            "The withheld amount: %s(%s%s), must be less than"
                            " tax amount %s(%s%s).") % (
                                tax.wh_tax, wh_line.wh_rate, porcent,
                                tax.base_wh, tax.base_wh * 100, porcent)
            if wh_line_ids and record.type == 'in_invoice':
                raise exceptions.except_orm(
                    _('Miscalculated Withheld Taxes'), note)
        if error_msg:
            raise exceptions.except_orm(_('Invalid action !'), error_msg)
        return True

    @api.multi
    def check_vat_wh(self):
        """ Check whether the invoice will need to be withheld taxes
        """
        res = {}
        for obj in self:
            if obj.type == 'out_invoice' and \
                    (not obj.date or not obj.date_accounting):
                raise exceptions.except_orm(
                    _('Error!'),
                    _('Must indicate: Accounting date and (or) Voucher Date'))
            for wh_line in obj.wh_lines:
                if not wh_line.tax_line:
                    res[wh_line.id] = (
                        wh_line.invoice_id.name,
                        wh_line.invoice_id.number,
                        wh_line.invoice_id.supplier_invoice_number)
        if res:
            note = _(
                'The Following Invoices Have not already been withheld:\n\n')
            for i in res:
                note += '* %s, %s, %s\n' % res[i]
            note += _('\nPlease, Load the Taxes to be withheld and Try Again')

            raise exceptions.except_orm(
                _('Invoices with Missing Withheld Taxes!'), note)
        return True

    @api.multi
    def check_invoice_nro_ctrl(self):
        """ Method that check if the control number of the invoice is set
        Return: True if the control number is set, and raise an exception
        when is not.
        """
        res = {}
        for obj in self:
            for wh_line in obj.wh_lines:
                if not wh_line.invoice_id.nro_ctrl:
                    res[wh_line.id] = (
                        wh_line.invoice_id.name,
                        wh_line.invoice_id.number,
                        wh_line.invoice_id.supplier_invoice_number)
        if res:
            note = _('The Following Invoices will not be withheld:\n\n')
            for i in res:
                note += '* %s, %s, %s\n' % res[i]
            note += _('\nPlease, Write the control number and Try Again')

            raise exceptions.except_orm(
                _('Invoices with Missing Control Number!'), note)
        return True

    @api.multi
    def write_wh_invoices(self):
        """ Method that writes the wh vat id in sale invoices.
        Return: True: write successfully.
                False: write unsuccessfully.
        """
        for obj in self:
            if obj.type in ('out_invoice', 'out_refund'):
                for wh_line in obj.wh_lines:
                    if not wh_line.invoice_id.write({'wh_itbms_id': obj.id}):
                        return False
        return True

    @api.multi
    @api.constrains('partner_id')
    def _check_partner(self):
        """ Determine if a given partner is a VAT Withholding Agent
        """
        partner = self.env['res.partner']
        for obj in self:
            if obj.type in ('out_invoice', 'out_refund'):
                if not partner._find_accounting_partner(
                        obj.partner_id).wh_agent_itbms:
                    raise exceptions.ValidationError(
                        _('The partner must be withholding vat agent .'))
            else:
                if not partner._find_accounting_partner(
                        obj.company_id.partner_id).wh_agent_itbms:
                    raise exceptions.ValidationError(
                        _('The partner must be withholding vat agent .'))

    _sql_constraints = [
        ('ret_num_uniq', 'unique (number,type,partner_id,company_id)',
         'number must be unique by partner and document type!')
    ]

    @api.multi
    def write(self, values):
        res = super(WhItbms, self).write(values)
        self._partner_invoice_check()
        return res

    @api.model
    def create(self, values):
        wh_itbms = super(WhItbms, self).create(values)
        wh_itbms._partner_invoice_check()
        return wh_itbms

    @api.multi
    def action_number(self):
        """ Update records numbers
        """
        # /!\ NOTE: FIX-ME
        return True
        for obj_ret in self:
            if obj_ret.type == 'in_invoice':
                self._cr.execute(
                    'SELECT id, number '
                    'FROM wh_itbms '
                    'WHERE id=%s' % (obj_ret.id))

                for (awi_id, number) in self._cr.fetchall():
                    if not number:
                        number = self.env['ir.sequence'].get(
                            'wh.itbms.%s' % obj_ret.type)
                    if not number:
                        raise exceptions.except_orm(
                            _("Missing Configuration !"),
                            _('No Sequence configured for Supplier'
                              ' VAT Withholding'))

                    self._cr.execute('UPDATE wh_itbms SET number=%s '
                                     'WHERE id=%s', (number, awi_id))
            return True

    @api.multi
    def action_date_accounting(self):
        """ Undated records will be assigned the current date
        """
        values = {}
        period = self.env['account.period']
        for wh in self:
            if wh.type in ['in_invoice']:
                values['date_accounting'] = \
                    wh.date or time.strftime('%Y-%m-%d')
                values['date'] = values['date_accounting']
                if not ((wh.period_id.id, wh.fortnight) ==
                        period.find_fortnight(values['date_accounting'])):
                    raise exceptions.except_orm(
                        _("Invalid action !"),
                        _("You have introduced non-valid accounting date. The"
                          "date needs to be in the same withholding period and"
                          " fortnigh."))
            elif wh.type in ['out_invoice']:
                values['date_accounting'] = \
                    wh.date_accounting or time.strftime('%Y-%m-%d')

            # if not wh.company_id.allow_vat_wh_outdated and \
            if values['date_accounting'] > time.strftime('%Y-%m-%d'):
                error_msg = _(
                    'You have introduced a non valid withholding date (a date \
                    in the future). The withholding date needs to be at least \
                    today or a previous date.')
                raise exceptions.except_orm(
                    _("Invalid action !"), _(error_msg))
            wh.write(values)
        return True

    @api.multi
    def action_move_create(self):
        """ Create movements associated with retention and reconcile
        """
        ctx = dict(self._context,
                   vat_wh=True,
                   company_id=self.env.user.company_id.id)
        for ret in self.with_context(ctx):
            for line in ret.wh_lines:
                if line.move_id or line.invoice_id.wh_itbms:
                    raise exceptions.except_orm(
                        _('Invoice already withhold !'),
                        _("You must omit the follow invoice '%s' !") %
                        (line.invoice_id.name))

            # TODO: Get rid of field in future versions?
            # We rather use the account in the invoice
            # acc_id = ret.account_id.id
            period_id = ret.period_id and ret.period_id.id or False
            journal_id = ret.journal_id.id
            if not period_id:
                period_id = self.env['account.period'].with_context(ctx).find(
                    ret.date_accounting or time.strftime('%Y-%m-%d'))
                if not period_id:
                    message = _("There are not Periods availables for the"
                                " pointed day, two options you must verify,"
                                " 1.- The period is closed, 2.- The period is"
                                " not created yet for your company")
                    raise exceptions.except_orm(_('Missing Periods!'), message)
                period_id = period_id[0]
            if ret.wh_lines:
                for line in ret.wh_lines:
                    writeoff_account_id, writeoff_journal_id = False, False
                    amount = line.wh_tax
                    if line.invoice_id.type in ['in_invoice', 'in_refund']:
                        name = ('COMP. RET. itbms ' + (ret.number or 'N/A') +
                                ' Doc. ' +
                                (line.invoice_id.supplier_invoice_number or
                                 str()))
                    else:
                        name = ('COMP. RET. itbms ' + ret.number + ' Doc. ' +
                                (line.invoice_id.number or str()))
                    acc_id = line.invoice_id.account_id.id
                    invoice = self.env['account.invoice'].with_context(
                        ctx).browse(line.invoice_id.id)
                    ret_move = invoice.ret_and_reconcile(
                        abs(amount), acc_id, period_id, journal_id,
                        writeoff_account_id, period_id, writeoff_journal_id,
                        ret.date_accounting, name, line.tax_line)

                    if (line.invoice_id.currency_id.id !=
                            line.invoice_id.company_id.currency_id.id):
                        exc = self.env['wh.itbms'].exc(
                            line.invoice_id.currency_id.id,
                            line.invoice_id.company_id.currency_id.id,
                            line.withholding_id.date)
                        for ml in self.env['account.move'].browse(
                                ret_move['move_id']).line_id:
                            ml.write({
                                'currency_id': line.invoice_id.currency_id.id})

                            if ml.credit:
                                ml.write({
                                    'amount_currency': exc(ml.credit) * -1})

                            elif ml.debit:
                                ml.write({
                                    'amount_currency': exc(ml.debit)})

                    # make the withholding line point to that move
                    rl = {'move_id': ret_move['move_id']}
                    lines = [(1, line.id, rl)]
                    ret.write({'wh_lines': lines,
                               'period_id': period_id})

                    if (rl and line.invoice_id.type
                            in ['out_invoice', 'out_refund']):
                        invoice.write({'wh_itbms_id': ret.id})
            return True

    @api.multi
    def on_change_date_accounting(self, date_accounting, date):
        res = {}
        if date_accounting:
            if not date:
                res.update({'date': date_accounting})
            period = self.env['account.period']
            period_id = period.find(date_accounting)
            res.update({'period_id': period_id and period_id[0]})
        return {'value': res}

    @api.multi
    def clear_wh_lines(self):
        """ Clear lines of current withholding document and delete wh document
        information from the invoice.
        """
        if self.ids:
            wil = self.env['wh.document.itbms'].search([
                ('withholding_id', 'in', self.ids)])
            invoice = wil.mapped("invoice_id")
            if invoice:
                invoice.write({'wh_itbms_id': False})
            if wil:
                wil.unlink()

        return True

    @api.multi
    def onchange_partner_id(self, inv_type, partner_id, period_id=False,
                            fortnight=False):
        """ Update the withholding document accounts and the withholding lines
        depending on the partner and another parameters that depend of the type
        of withholdong. If the type is sale will only take into account the
        partner, but if the type is purchase would take into account the period
        and fortnight changes.

        This method delete lines at right moment and unlink/link the
        withholding document to the related invoices.
        @param type: invoice type
        @param partner_id: partner_id at current view
        @param period_id: period_id at current view
        @param fortnight: fortnight at current view
        """
        period = self.env['account.period']
        partner = self.env['res.partner']
        values_data = {}
        acc_id = False
        wh_type = inv_type in ('out_invoice', 'out_refund') and 'sale' or \
            'purchase'

        # clear lines
        self.clear_wh_lines()

        # pull account info
        if partner_id:
            acc_part_id = partner._find_accounting_partner(
                partner.browse(partner_id))
            if wh_type == 'sale':
                acc_id = (acc_part_id.property_account_receivable and
                          acc_part_id.property_account_receivable.id or False)
            else:
                acc_id = (acc_part_id.property_account_payable and
                          acc_part_id.property_account_payable.id or False)
            values_data['account_id'] = acc_id
        else:
            return {'value': values_data}

        # add lines
        ttype = wh_type == 'sale' and ['out_invoice', 'out_refund'] \
            or ['in_invoice', 'in_refund']
        invoices = self.env['account.invoice'].search([
            ('state', '=', 'open'), ('wh_itbms', '=', False),
            ('wh_itbms_id', '=', False), ('type', 'in', ttype),
            '|',
            ('partner_id', '=', acc_part_id.id),
            ('partner_id', 'child_of', acc_part_id.id),
            ('period_id', '=', period_id)])

        if wh_type == 'purchase':
            invoices = invoices.filtered(
                lambda r: period.find_fortnight(r.date_invoice) ==
                (period_id, fortnight))
        # search withholdable invoices
        new_invoices = invoices.filtered("tax_line.tax_id.wh")
        if new_invoices:
            values_data['wh_lines'] = \
                [{'invoice_id': inv.id,
                  'name': inv.name or _('N/A'),
                  'wh_rate': partner._find_accounting_partner(
                      inv.partner_id).wh_rate_itbms}
                 for inv in new_invoices]
            # TODO: integrate to the dictionary the value like this:
            # """'consolidate_vat_wh': partner._find_accounting_partner(
            #           inv.partner_id).consolidate_vat_wh,"""
            # This only applies in purchase.
        return {'value': values_data}

    @api.multi
    def _partner_invoice_check(self):
        """ Verify that the partner associated of the invoice is correct
        @param values: Contain withholding lines, partner id and invoice_id
        """
        partner = self.env['res.partner']
        for record in self:
            inv_str = str()
            for line in record.wh_lines:
                acc_part_id = partner._find_accounting_partner(
                    line.invoice_id.partner_id)
                if acc_part_id.id != record.partner_id.id:
                    inv_str += '%s' % '\n' + (
                        line.invoice_id.name or
                        line.invoice_id.number or '')

            if inv_str:
                raise exceptions.except_orm(
                    _('Incorrect Invoices !'),
                    _("The following invoices are not from the selected"
                      " partner: %s ") % (inv_str))

        return True

    @api.multi
    def check_wh_lines_fortnights(self):
        """Check that every wh itbms line belongs to the wh itbms fortnight."""
        period = self.env['account.period']
        error_msg = str()
        fortnight_str = {'True': ' - Second Fortnight)',
                         'False': ' - First Fortnight)'}
        for awi_brw in self:
            if awi_brw.type in ['out_invoice']:
                return True
            for awil_brw in awi_brw.wh_lines:
                awil_period_id, awil_fortnight = period.find_fortnight(
                    awil_brw.invoice_id.date_invoice)
                if awil_period_id != awi_brw.period_id.id or \
                   awil_fortnight != awi_brw.fortnight:
                    error_msg += \
                        (" * Line '" + awil_brw.invoice_id.number +
                         "' belongs to (" +
                         period.browse(awil_period_id).name +
                         fortnight_str[awil_fortnight] +
                         ".\n")
            if error_msg:
                raise exceptions.except_orm(
                    _("Invalid action !"),
                    _("Some withholding lines being withheld dont match"
                      " with the withholding document period and"
                      " fortnight.\n\n * Withholding VAT document correspond"
                      " to (" + awi_brw.period_id.name + fortnight_str[
                          awi_brw.fortnight] + ".\n\n" + error_msg))
            else:
                return True

    @api.multi
    def compute_amount_wh(self):
        """ Calculate withholding amount each line
        """
        if self.check_wh_lines_fortnights():
            for retention in self:
                whl_ids = [line.id for line in retention.wh_lines]
                if whl_ids:
                    awil = self.env['wh.document.itbms'].browse(whl_ids)
                    awil.load_taxes()
        return True

    @api.multi
    def _dummy_cancel_check(self):
        '''
        This will be the method that another developer should use to create new
        check on Withholding Document
        Make super to this method and create your own cases
        '''
        return True

    @api.multi
    def _check_tax_iva_lines(self):
        """Check if this itbms WH DOC is being used in a TXT itbms DOC"""
        til = self.env["txt.itbms.line"].search([
            ('txt_id.state', '!=', 'draft'),
            ('voucher_id', 'in', self.ids)])

        if not til:
            return True

        note = _('The Following itbms TXT DOC should be set to Draft before'
                 ' Cancelling this Document\n\n')
        ti_ids = list(set([til_brw.txt_id.id for til_brw in til]))
        for ti_brw in self.env['txt.itbms'].browse(ti_ids):
            note += '%s\n' % ti_brw.name
            raise exceptions.except_orm(_("Invalid Procedure!"), note)

    @api.multi
    def cancel_check(self):
        '''
        Unique method to check if we can cancel the Withholding Document
        '''

        if not self._check_tax_iva_lines():
            return False
        if not self._dummy_cancel_check():
            return False
        return True

    @api.multi
    def _dummy_confirm_check(self):
        '''
        This will be the method that another developer should use to create new
        check on Withholding Document
        Make super to this method and create your own cases
        '''
        return True

    @api.multi
    def confirm_check(self):
        '''
        Unique method to check if we can confirm the Withholding Document
        '''

        if (not self.check_wh_lines() or
                # not self.check_wh_lines_fortnights() or
                # not self.check_invoice_nro_ctrl() or
                not self.check_vat_wh() or
                not self.check_wh_taxes() or
                not self.write_wh_invoices() or
                not self._dummy_confirm_check()):
            return False
        return True

    @api.multi
    def check_wh_lines(self):
        """ Check that wh itbms has lines to withhold."""
        for awi_brw in self:
            if not awi_brw.wh_lines:
                raise exceptions.except_orm(
                    _("Missing Values !"),
                    _("Missing Withholding Lines!!!"))
        return True

    @api.multi
    def copy(self, default=None):
        """ Update fields when duplicating
        """
        # NOTE: use ids argument instead of id for fix the pylint error W0622.
        # Redefining built-in 'id'
        if not default:
            default = {}
        for record in self:
            if record.type == 'in_invoice':
                raise exceptions.except_orm(
                    _('Alert !'),
                    _('you can not duplicate this document!!!'))

        default.update({
            'state': 'draft',
            'number': False,
            'code': False,
            'wh_lines': [],
            'period_id': False
        })

        return super(WhItbms, self).copy(default)

    @api.multi
    def unlink(self):
        """ Overwrite the unlink method to throw an exception if the
        withholding is not in cancel state."""
        for awi_brw in self:
            if awi_brw.state != 'cancel':
                raise exceptions.except_orm(
                    _("Invalid Procedure!!"),
                    _("The withholding document needs to be in cancel state"
                      " to be deleted."))
            else:
                awi_brw.clear_wh_lines()
        return super(WhItbms, self).unlink()
