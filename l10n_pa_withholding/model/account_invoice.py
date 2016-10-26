# coding: utf-8
# Copyright 2016 Vauxoo (https://www.vauxoo.com) <info@vauxoo.com>
from __future__ import division
from openerp import api, fields, models, _
from openerp.exceptions import except_orm


class AccountInvoice(models.Model):
    _inherit = 'account.invoice'
    wh_move_id = fields.Many2one(
        'account.move',
        string='Withholding Journal Entry',
        readonly=True,
        index=True,
        copy=False,
        help="Link to the automatically generated Withholding Journal Entry.")
    # /!\ NOTE: This code will be regarded as duplicated
    l10n_pa_wh_subject = fields.Selection([
        ('na', 'No Aplica'),
        (1, 'Pago por Servicio Profesional al Estado 100%'),
        (2, 'Pago por Venta de Bienes/Servicios al Estado 50%'),
        (3, 'Pago o Acreditacion a No Domiciliado o Empresa Constituida en el'
         ' Exterior 100%'),
        (4, 'Pago o Acreditacion por Compra de Bienes/Servicios 50%'),
        (5, 'Pago a Comercio Afiliado a Sistema de TC/TD 2%'),
        (6, 'Pago a Comercio Afiliado a Sistema de TC/TD 1%'),
        (7, 'Pago a Comercio Afiliado a Sistema de TC/TD 50%')],
        string='ITBMS Withholding Subject',
        help='If Apply. Indicates how much ITBMS to withholding on Payment')

    @api.model
    def wh_tax_account(self, line):
        return line.account_id.id

    @api.model
    def wh_move_line_get_item(self, line):
        if line.invoice_id.type == 'out_invoice':
            sign = -1
        elif line.invoice_id.type == 'out_refund':
            sign = 1
        return {
            'type': 'src',
            'name': line.name.split('\n')[0][:64],
            'account_id': self.wh_tax_account(line),
            'price': sign * line.amount,  # TODO: Insert Withheld value here!
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
            'tax_line_id': line.get('tax_line_id', False),
        }

    @api.model
    def wh_move_line_get(self):
        # /!\ TODO: Invoice to be ommited for Withholding
        # return []
        # /!\ TODO: Determine if withholding will proceed because of the
        # Withholding Agent Entitlement
        res = []
        if self.type not in ('out_invoice', 'out_refund'):
            return res
        if not self.tax_line:
            return res
        for tax_brw in self.tax_line:
            if not tax_brw.amount:
                continue
            res.append(self.wh_move_line_get_item(tax_brw))
        return res

    @api.multi
    def action_move_create_withholding(self):
        """Creates Withholding for taxes in invoice"""
        account_move = self.env['account.move']

        for invoice_brw in self:
            if not invoice_brw.tax_line:
                continue
            if invoice_brw.wh_move_id:
                continue
            if not invoice_brw.l10n_pa_wh_subject:
                raise except_orm(
                    _('Error!'),
                    _('Please define a Withholding Subject to this invoice.'))
            if invoice_brw.l10n_pa_wh_subject == 'na':
                continue
            ctx = dict(self._context, lang=invoice_brw.partner_id.lang)
            journal = invoice_brw.journal_id.with_context(ctx)
            date = invoice_brw.date_invoice

            ref = invoice_brw.reference or invoice_brw.name,
            company_currency = invoice_brw.company_id.currency_id
            ait = invoice_brw.wh_move_line_get()

            if not ait:
                continue

            total, total_currency, ait = invoice_brw.with_context(
                ctx).compute_invoice_totals(company_currency, ref, ait)

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
