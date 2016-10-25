# coding: utf-8
# Copyright 2016 Vauxoo (https://www.vauxoo.com) <info@vauxoo.com>
from __future__ import division
from openerp import api, fields, models


class AccountInvoice(models.Model):
    _inherit = 'account.invoice'
    wh_move_id = fields.Many2one(
        'account.move',
        string='Withholding Journal Entry',
        readonly=True,
        index=True,
        copy=False,
        help="Link to the automatically generated Withholding Journal Entry.")

    @api.model
    def wh_tax_account(self, line):
        return line.account_id.id

    @api.model
    def wh_move_line_get_item(self, line):
        return {
            'type': 'src',
            'name': line.name.split('\n')[0][:64],
            'account_id': self.wh_tax_account(line),
            'price': line.amount,
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
            'tax_line_id': line.get('tax_line_id', False),
        }

    @api.model
    def wh_move_line_get(self):
        res = []
        for tax_brw in self.tax_line:
            debit = self.wh_move_line_get_item(tax_brw)
            res.append(debit)
        return res

    @api.multi
    def compute_tax_totals(self, company_currency, ref, ait):
        total = 0
        total_currency = 0
        currency = self.currency_id.with_context(
            date=self.date_invoice or fields.Date.context_today(self))
        for line in ait:
            line['ref'] = ref
            line['currency_id'] = False
            line['amount_currency'] = False
            if self.currency_id != company_currency:
                line['currency_id'] = currency.id
                line['amount_currency'] = currency.round(line['price'])
                line['price'] = currency.compute(
                    line['price'], company_currency)
            if self.type in ('out_invoice', 'in_refund'):
                total += line['price']
                total_currency += line['amount_currency'] or line['price']
                line['price'] = - line['price']
            else:
                total -= line['price']
                total_currency -= line['amount_currency'] or line['price']
        return total, total_currency, ait

    @api.multi
    def action_move_create_withholding(self):
        """Creates Withholding for taxes in invoice"""
        account_move = self.env['account.move']

        for invoice_brw in self:
            if not invoice_brw.tax_line:
                continue
            if invoice_brw.wh_move_id:
                continue
            ctx = dict(self._context, lang=invoice_brw.partner_id.lang)
            journal = invoice_brw.journal_id.with_context(ctx)
            date = invoice_brw.date_invoice

            ref = invoice_brw.reference or invoice_brw.name,
            company_currency = invoice_brw.company_id.currency_id
            ait = invoice_brw.wh_move_line_get()

            total, total_currency, ait = invoice_brw.with_context(
                ctx).compute_tax_totals(company_currency, ref, ait)

            name = invoice_brw.supplier_invoice_number or \
                invoice_brw.name or '/'

            if total:
                company_currency = invoice_brw.company_id.currency_id
                diff_curr = invoice_brw.currency_id != company_currency
                ait.append({
                    'type': 'dest',
                    'name': name,
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

            # line = invoice_brw.finalize_tax_move_lines(line)

            move_vals = {
                'ref': invoice_brw.reference or invoice_brw.name,
                'line_id': line,
                'journal_id': journal.id,
                'date': date,
                'company_id': invoice_brw.company_id.id,
                'name': '%s-WH' % invoice_brw.move_id.name,
            }
            ctx['company_id'] = invoice_brw.company_id.id
            period = invoice_brw.period_id.with_context(ctx).find(date)[:1]
            if period:
                move_vals['period_id'] = period.id
                for i in line:
                    i[2]['period_id'] = period.id

            ctx_nolang = ctx.copy()
            ctx_nolang.pop('lang', None)
            move = account_move.with_context(ctx_nolang).create(move_vals)

            # make the tax point to that move
            vals = {
                'wh_move_id': move.id,
                'period_id': period.id,
            }
            invoice_brw.with_context(ctx).write(vals)
            # Pass tax in context in method post: used if you want to get
            # the same
            # account move reference when creating the same tax after a
            # cancelled one:
            move.post()
        # TODO self._log_event()
        return True
