# coding: utf-8

import time

from openerp.addons import decimal_precision as dp
from openerp import models, fields, api, exceptions, _


class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    @api.multi
    @api.depends('wh_itbms_id.wh_lines')
    def _compute_wh_itbms_id(self):
        for record in self:
            lines = self.env['wh.document.itbms'].search([
                ('invoice_id', '=', record.id)])
            record.wh_itbms_id = lines and lines[0].withholding_id.id or False

    @api.multi
    @api.depends(
        'move_id.line_id.reconcile_id.line_id',
        'move_id.line_id.reconcile_partial_id.line_partial_ids',
    )
    def _compute_retenida(self):
        """ Verify whether withholding was applied to the invoice
        """
        for record in self:
            try:
                record.wh_itbms = record.test_retenida()
            except:
                record.wh_itbms = False

    @api.multi
    def check_withholding_duplicate(self):
        """
        check that invoice not have a withholding vat created previously.
        @return True or False.
        """
        wdi_obj = self.env['wh.document.itbms']
        for inv_brw in self:
            if wdi_obj.search([('invoice_id', '=', inv_brw.id)]):
                return False
        return True

    @api.multi
    def check_document_date(self):
        """
        check that the invoice in open state have the document date defined.
        @return True or raise an osv exception.
        """
        for inv_brw in self:
            if (inv_brw.type in ('in_invoice', 'in_refund') and
                    inv_brw.state == 'open' and not inv_brw.date_document):
                raise exceptions.except_orm(
                    _('Warning'),
                    _('The document date can not be empty when the invoice is'
                      ' in open state.'))
        return True

    @api.multi
    def check_invoice_dates(self):
        """
        check that the date document is less or equal than the date invoice.
        @return True or raise and osv exception.
        """
        for inv_brw in self:
            if (inv_brw.type in ('in_invoice', 'in_refund') and
                    inv_brw.date_document and
                    not inv_brw.date_document <= inv_brw.date_invoice):
                raise exceptions.except_orm(
                    _('Warning'),
                    _('The document date must be less or equal than the'
                      ' invoice date.'))
        return True

    wh_itbms = fields.Boolean(
        string='Withhold',
        compute='_compute_retenida', store=True,
        help="The account moves of the invoice have been retention with"
        " account moves of the payment(s).")
    wh_itbms_id = fields.Many2one(
        'wh.itbms', string='ITBMS Wh. Document',
        compute='_compute_wh_itbms_id', store=True,
        help="This is the ITBMS Withholding Document where this invoice"
                " is being withheld")
    itbms_apply = fields.Boolean(
        string='Exclude this document from VAT Withholding',
        states={'draft': [('readonly', False)]},
        help="This selection indicates whether generate the invoice"
        " withholding document")
    consolidate_itbms_wh = fields.Boolean(
        string='Group ITBMS Withholdings', readonly=True,
        states={'draft': [('readonly', False)]}, default=False,
        help="This selection indicates to group this invoice in existing"
        " withholding document")

    @api.multi
    def copy(self, default=None):
        """ Initialized fields to the copy a register """
        default = dict(default or {})
        # TODO: PROPERLY CALL THE wh_rate_itbms
        default.update({'wh_itbms': False,
                        'wh_itbms_id': False,
                        'itbms_apply': False})
        return super(AccountInvoice, self).copy(default)

    @api.multi
    def wh_itbms_line_create(self):
        """ Creates line with itbms withholding
        """
        wdi_obj = self.env['wh.document.itbms']
        partner = self.env['res.partner']
        values = {}
        for inv_brw in self:
            wh_rate_itbms = (
                inv_brw.type in ('in_invoice', 'in_refund') and
                partner._find_accounting_partner(
                    inv_brw.partner_id).wh_rate_itbms or
                partner._find_accounting_partner(
                    inv_brw.company_id.partner_id).wh_rate_itbms)
            values = {'name': inv_brw.name or inv_brw.number,
                      'invoice_id': inv_brw.id,
                      'wh_rate_itbms': wh_rate_itbms}
        return values and wdi_obj.create(values)

    @api.multi
    def action_wh_itbms_supervisor(self):
        """ Validate the currencys are equal
        """
        for inv in self:
            if inv.amount_total == 0.0:
                raise exceptions.except_orm(
                    _('Invalid Action !'),
                    _('This invoice has total amount %s %s check the'
                      ' products price') % (inv.amount_total,
                                            inv.currency_id.symbol))
        return True

    @api.multi
    def get_fortnight_wh_id(self):
        """ Returns the id of the wh.itbms in draft state that correspond to
        the invoice fortnight. If not exist return False.
        """
        wh_itbms_obj = self.env['wh.itbms']
        period = self.env['account.period']
        partner = self.env['res.partner']
        for inv_brw in self:
            date_invoice = inv_brw.date_invoice
            acc_part_id = partner._find_accounting_partner(inv_brw.partner_id)
            inv_period, inv_fortnight = period.find_fortnight(date_invoice)
            ttype = inv_brw.type in ["out_invoice", "out_refund"] \
                and "out_invoice" or "in_invoice"
            for wh_itbms in wh_itbms_obj.search([
                    ('state', '=', 'draft'), ('type', '=', ttype), '|',
                    ('partner_id', '=', acc_part_id.id),
                    ('partner_id', 'child_of', acc_part_id.id),
                    ('period_id', '=', inv_period),
                    ('fortnight', '=', inv_fortnight)]):
                return wh_itbms.id
        return False

    @api.multi
    def create_new_wh_itbms(self, ret_line_id):
        """ Create a Withholding VAT document.
        @param ids: only one id.
        @param ret_line_id: wh.itbms id.
        @return id of the new wh vat document created.
        """
        wh_itbms_obj = self.env['wh.itbms']
        per_obj = self.env['account.period']
        rp_obj = self.env['res.partner']
        wh_itbms = {}
        for inv_brw in self:
            acc_part_id = rp_obj._find_accounting_partner(inv_brw.partner_id)
            if inv_brw.type in ('out_invoice', 'out_refund'):
                acc_id = acc_part_id.property_account_receivable.id
                wh_type = 'out_invoice'
            else:
                acc_id = acc_part_id.property_account_payable.id
                wh_type = 'in_invoice'
                if not acc_id:
                    raise exceptions.except_orm(
                        _('Invalid Action !'),
                        _('You need to configure the partner with'
                          ' withholding accounts!'))
            wh_itbms = {
                'name': _('ITBMS WH - ORIGIN %s' % (inv_brw.number)),
                'type': wh_type,
                'account_id': acc_id,
                'partner_id': acc_part_id.id,
                'period_id': inv_brw.period_id.id,
                'wh_lines': [(4, ret_line_id.id)],
                'fortnight': per_obj.find_fortnight(inv_brw.date_invoice)[1],
            }
            if inv_brw.company_id.propagate_invoice_date_to_vat_withholding:
                wh_itbms['date'] = inv_brw.date_invoice
        return wh_itbms and wh_itbms_obj.create(wh_itbms) or False

    @api.multi
    def action_wh_itbms_create(self):
        """ Create withholding objects """
        for inv in self:
            if inv.wh_itbms_id:
                if inv.wh_itbms_id.state == 'draft':
                    inv.wh_itbms_id.compute_amount_wh()
                else:
                    raise exceptions.except_orm(
                        _('Warning !'),
                        _('You have already a withholding doc associate to'
                          ' your invoice, but this withholding doc is not in'
                          ' cancel state.'))
            else:
                # Create Lines Data
                ret_id = False
                ret_line_id = inv.wh_itbms_line_create()
                fortnight_wh_id = inv.get_fortnight_wh_id()
                # Add line to a WH DOC
                if inv.company_id.consolidate_vat_wh and fortnight_wh_id:
                    # Add to an exist WH Doc
                    ret_id = fortnight_wh_id
                    if not ret_id:
                        raise exceptions.except_orm(
                            _('Error!'),
                            _('Can\'t find withholding doc'))
                    wh_itbms = self.env['wh.itbms'].browse(ret_id)
                    wh_itbms.write({'wh_lines': [(4, ret_line_id)]})
                else:
                    # Create a New WH Doc and add line
                    ret_id = inv.create_new_wh_itbms(ret_line_id)
                if ret_id:
                    inv.write({'wh_itbms_id': ret_id.id})
                    inv.wh_itbms_id.compute_amount_wh()
        return True

    @api.multi
    def button_reset_taxes_ret(self):
        """ Recalculate taxes in invoice
        """
        account_invoice_tax = self.env['account.invoice.tax']
        for inv in self:
            compute_taxes_ret = account_invoice_tax.compute_wh_tax(inv)
            for tax in account_invoice_tax.browse(compute_taxes_ret.keys()):
                tax.write(compute_taxes_ret[tax.id])
        return True

    @api.multi
    def button_reset_taxes(self):
        """ It makes two function calls related taxes reset
        """
        res = super(AccountInvoice, self).button_reset_taxes()
        self.button_reset_taxes_ret()
        return res

    @api.multi
    def _withholding_partner(self):
        """ I verify that the provider retains or not
        """
        # No VAT withholding Documents are created for customer invoice &
        # refunds
        for inv in self:
            if inv.type in ('in_invoice', 'in_refund') and \
                    self.env['res.partner']._find_accounting_partner(
                        inv.company_id.partner_id).wh_itbms_agent:
                return True
        return False

    @api.multi
    def _withholdable_tax(self):
        """ Verify that existing withholding in invoice
        """
        for inv in self:
            return any([line.tax_id.ret for line in inv.tax_line])
        return False

    @api.multi
    def check_withholdable(self):
        """ This will test for Refund invoice trying to find out
        if its regarding parent is in the same fortnight.

        return True if invoice is type 'in_invoice'
        return True if invoice is type 'in_refund' and parent_id invoice
                are both in the same fortnight.
        return False otherwise
        """
        period = self.env['account.period']
        for inv in self:
            if inv.type == 'in_invoice':
                return True
            if inv.type == 'in_refund' and inv.parent_id:
                dt_refund = inv.date_invoice or time.strftime('%Y-%m-%d')
                dt_invoice = inv.parent_id.date_invoice
                return period.find_fortnight(dt_refund) == \
                    period.find_fortnight(dt_invoice)
        return False

    @api.multi
    def check_wh_apply(self):
        """ Apply withholding to the invoice
        """
        wh_apply = []
        for inv in self:
            if inv.itbms_apply:
                return False
            wh_apply.append(inv._withholdable_tax())
            wh_apply.append(inv._withholding_partner())
        return all(wh_apply)

    @api.multi
    def _get_move_lines(self, to_wh, period_id, pay_journal_id,
                        writeoff_acc_id, writeoff_period_id,
                        writeoff_journal_id, date, name):
        """ Generate move lines in corresponding account
        @param to_wh: whether or not withheld
        @param period_id: Period
        @param pay_journal_id: pay journal of the invoice
        @param writeoff_acc_id: account where canceled
        @param writeoff_period_id: period where canceled
        @param writeoff_journal_id: journal where canceled
        @param date: current date
        @param name: description
        """
        res = super(AccountInvoice, self)._get_move_lines(
            to_wh, period_id, pay_journal_id, writeoff_acc_id,
            writeoff_period_id, writeoff_journal_id, date, name)
        if self._context.get('vat_wh'):
            for invoice in self:
                acc_part_id = \
                    self.env['res.partner']._find_accounting_partner(
                        invoice.partner_id)

                types = {'out_invoice': -1,
                         'in_invoice': 1,
                         'out_refund': 1,
                         'in_refund': -1}
                direction = types[invoice.type]

                for tax_brw in to_wh:
                    if 'invoice' in invoice.type:
                        acc = (tax_brw.tax_id.wh_vat_collected_account_id and
                               tax_brw.tax_id.wh_vat_collected_account_id.id or
                               False)
                    elif 'refund' in invoice.type:
                        acc = (tax_brw.tax_id.wh_vat_paid_account_id and
                               tax_brw.tax_id.wh_vat_paid_account_id.id or
                               False)
                    if not acc:
                        raise exceptions.except_orm(
                            _('Missing Account in Tax!'),
                            _("Tax [%s] has missing account. Please, fill the"
                              " missing fields") % (tax_brw.tax_id.name))
                    res.append((0, 0, {
                        'debit':
                        direction * tax_brw.wh_tax < 0 and
                        direction * tax_brw.wh_tax,
                        'credit':
                        direction * tax_brw.wh_tax > 0 and
                        direction * tax_brw.wh_tax,
                        'account_id': acc,
                        'partner_id': acc_part_id.id,
                        'ref': invoice.number,
                        'date': date,
                        'currency_id': False,
                        'name': name
                    }))
        return res

    @api.multi
    def validate_wh_itbms_done(self):
        """ Method that check if wh vat is validated in invoice refund.
        @params: ids: list of invoices.
        return: True: the wh vat is validated.
                False: the wh vat is not validated.
        """
        for inv in self:
            if inv.type in ('out_invoice', 'out_refund') and \
                    not inv.wh_itbms_id:
                wh_itbms = True
            else:
                wh_itbms = (not inv.wh_itbms_id and True or
                            inv.wh_itbms_id.state in ('done') and
                            True or False)
                if not wh_itbms:
                    raise exceptions.except_orm(
                        _('Error !'),
                        _('The withholding VAT "%s" is not validated!' %
                          inv.wh_itbms_id.code))
        return True

    @api.multi
    def button_generate_wh_doc(self):
        context = self._context
        partner = self.env['res.partner']
        res = {}
        for inv in self:
            view_id = self.env['ir.ui.view'].search([
                ('name', '=', 'wh.itbms.form.customer')])
            context.update({
                'invoice_id': inv.id,
                'type': inv.type,
                'default_partner_id': partner._find_accounting_partner(
                    inv.partner_id).id,
                'default_name': inv.name or inv.number,
                'view_id': view_id,
            })
            res = {
                'name': _('Withholding vat customer'),
                'type': 'ir.actions.act_window',
                'res_model': 'wh.itbms',
                'view_type': 'form',
                'view_id': False,
                'view_mode': 'form',
                'nodestroy': True,
                'target': 'current',
                'domain': "[('type', '=', '" + inv.type + "')]",
                'context': context
            }
        return res

    @api.multi
    def action_cancel(self):
        """ Verify first if the invoice have a non cancel withholding doc.
        If it has then raise a error message. """
        for inv in self:
            if ((not inv.wh_itbms_id) or (
                    inv.wh_itbms_id and
                    inv.wh_itbms_id.state == 'cancel')):
                super(AccountInvoice, self).action_cancel()
            else:
                raise exceptions.except_orm(
                    _("Error!"),
                    _("You can't cancel an invoice that have non cancel"
                      " withholding document. Needs first cancel the invoice"
                      " withholding document and then you can cancel this"
                      " invoice."))
        return True


class AccountInvoiceTax(models.Model):
    _inherit = 'account.invoice.tax'

    # /!\ NOTE: `wh_tax` used to be `amount_ret`
    wh_tax = fields.Float(
        string='Withheld Tax',
        digits=dp.get_precision('Withhold'),
        help="Withheld Tax")
    # /!\ NOTE: `base_tax` used to be `base_ret`
    base_tax = fields.Float(
        string='Tax Base', digits=dp.get_precision('Withhold'),
        help="Tax Base. Untaxed Amount")

    @api.model
    def compute_wh_tax(self, invoice):
        """ Calculate withholding amount """
        res = {}
        partner = self.env['res.partner']
        acc_part_id = invoice.type in ['out_invoice', "out_refund"] and \
            partner._find_accounting_partner(invoice.company_id.partner_id) \
            or partner._find_accounting_partner(invoice.partner_id)
        wh_rate_itbms = acc_part_id.wh_rate_itbms

        for record in invoice.tax_line:
            wh_tax = 0.0
            if record.tax_id.wh:
                wh_tax = (wh_rate_itbms and
                          record.tax_amount * wh_rate_itbms / 100.0 or 0.00)
            res[record.id] = {'wh_tax': wh_tax, 'base_tax': record.base_amount}
        return res
