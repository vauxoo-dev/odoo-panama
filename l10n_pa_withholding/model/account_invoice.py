# coding: utf-8
# Copyright 2016 Vauxoo (https://www.vauxoo.com) <info@vauxoo.com>
from __future__ import division
from openerp import api, fields, models, _
from openerp.exceptions import except_orm


class AccountInvoice(models.Model):
    _name = 'account.invoice'
    _inherit = ['account.invoice', 'l10n.pa.common.abstract']
    wh_move_id = fields.Many2one(
        'account.move',
        string='Withholding Journal Entry',
        readonly=True,
        index=True,
        copy=False,
        help="Link to the automatically generated Withholding Journal Entry.")

    @api.model
    def wh_tax_account(self, line):
        account_id = line.invoice_id.company_id.wh_sale_itbms_account_id
        if not account_id:
            raise except_orm(
                _('Error!'),
                _('Please Define an Account to be used for withholding ITBMS '
                  'on Customer Invoice on Your Company.'))
        return account_id.id

    @api.model
    def wh_move_line_get_item(self, line, wh_val):
        sign = -1 if 'out' in line.invoice_id.type else 1
        return {
            'type': 'src',
            'name': line.name.split('\n')[0][:64],
            'account_id': self.wh_tax_account(line),
            'price': sign * line.amount * wh_val / 100.0,
            'tax_code_id': line.tax_code_id.id,
            'tax_amount': line.amount,
        }

    @api.model
    def wh_line_get_convert(self, line, part, date):
        return {
            'partner_id': part,
            'name': line['name'][:64],
            'date': date,
            'debit': line['price'] > 0 and line['price'],
            'credit': line['price'] < 0 and -line['price'],
            'account_id': line['account_id'],
            'analytic_lines': line.get('analytic_lines', []),
            'amount_currency': line['price'] > 0 and abs(
                line.get('amount_currency', False)) or -abs(
                    line.get('amount_currency', False)),
            'currency_id': line.get('currency_id', False),
            'tax_code_id': line.get('tax_code_id', False),
            'tax_amount': line.get('tax_amount', False),
            'ref': line.get('ref', False),
            'analytic_account_id': line.get('account_analytic_id', False),
            # 'tax_line_id': line.get('tax_line_id', False),
        }

    @api.model
    def wh_move_line_get(self, wh_val):
        # /!\ TODO: Invoice to be ommited for Withholding
        # return []
        # /!\ TODO: Determine if withholding will proceed because of the
        # Withholding Agent Entitlement
        res = []
        for tax_brw in self.tax_line:
            if not tax_brw.amount:
                continue
            res.append(self.wh_move_line_get_item(tax_brw, wh_val))
        return res

    @api.multi
    def wh_subject_mapping(self, val):
        res = dict([
            ('1', 100), ('2', 50), ('3', 100),
            ('4', 50), ('5', 2), ('6', 1), ('7', 50)])
        return res.get(val, 0.0)

    @api.multi
    def action_move_create_withholding(self):
        """Creates Withholding for taxes in invoice"""
        account_move = self.env['account.move']

        for invoice_brw in self:
            if invoice_brw.type not in ('out_invoice', 'out_refund'):
                continue
            if not invoice_brw.tax_line:
                continue
            if not invoice_brw.wh_agent_itbms:
                continue
            if invoice_brw.wh_move_id:
                continue
            if not invoice_brw.l10n_pa_wh_subject:
                raise except_orm(
                    _('Error!'),
                    _('Please define a Withholding Subject to this invoice.'))
            if invoice_brw.l10n_pa_wh_subject == 'na':
                continue

            journal = invoice_brw.company_id.wh_sale_itbms_journal_id
            if not journal:
                raise except_orm(
                    _('Error!'),
                    _('Please Define a Journal to be used for withholding '
                      'ITBMS on Customer Invoice on Your Company.'))

            ctx = dict(self._context, lang=invoice_brw.partner_id.lang)
            date = invoice_brw.date_invoice

            ref = invoice_brw.reference or invoice_brw.name,
            company_currency = invoice_brw.company_id.currency_id
            wh = self.wh_subject_mapping(self.l10n_pa_wh_subject)
            ait = invoice_brw.wh_move_line_get(wh)

            if not ait:
                continue

            total, total_currency, ait = invoice_brw.with_context(
                ctx).compute_invoice_totals(company_currency, ref, ait)

            if total:
                company_currency = invoice_brw.company_id.currency_id
                diff_curr = invoice_brw.currency_id != company_currency
                ait.append({
                    'type': 'dest',
                    'name': _('ITBMS Withheld on Invoice'),
                    'price': total,
                    'account_id': invoice_brw.account_id.id,
                    'date_maturity': invoice_brw.date_due,
                    'amount_currency': diff_curr and total_currency,
                    'currency_id': diff_curr and invoice_brw.currency_id.id,
                    'ref': ref
                })

            part = self.env['res.partner']._find_accounting_partner(
                invoice_brw.partner_id)

            line = [
                (0, 0,
                 self.wh_line_get_convert(l, part.id, date)) for l in ait]

            move_vals = {
                'ref': invoice_brw.reference or invoice_brw.name,
                'line_id': line,
                'journal_id': journal.id,
                'date': date,
                'company_id': invoice_brw.company_id.id,
            }
            ctx['company_id'] = invoice_brw.company_id.id

            move_vals['period_id'] = invoice_brw.period_id.id
            for i in line:
                i[2]['period_id'] = invoice_brw.period_id.id

            ctx_nolang = ctx.copy()
            ctx_nolang.pop('lang', None)
            move = account_move.with_context(ctx_nolang).create(move_vals)

            invoice_brw.write({'wh_move_id': move.id})
        return True

    @api.multi
    def wihholding_reconciliation(self):
        """Reconciles Journal Items from wh_move_id with those in move_id on
        Invoice"""

        for inv_brw in self:
            move_ids = [move.id or False
                        for move in (inv_brw.move_id, inv_brw.wh_move_id)]

            if not all(move_ids):
                continue

            line_ids = [line.id
                        for move2 in (inv_brw.move_id, inv_brw.wh_move_id)
                        for line in move2.line_id
                        if line.account_id.id == inv_brw.account_id.id]

            if len(line_ids) < 2:
                continue

            # /!\ NOTE: There could be some payments in the invoice let us
            # reconcile them too
            line_ids += [lin2.id for lin2 in inv_brw.payment_ids]
            line_ids = list(set(line_ids))

            line_ids = self.env['account.move.line'].browse(line_ids)
            line_ids.reconcile_partial()

        return True
