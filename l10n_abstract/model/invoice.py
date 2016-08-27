# coding: utf-8

import time
from openerp import api
from openerp.osv import fields, osv
from openerp.tools.translate import _


class AccountInvoice(osv.osv):
    _inherit = 'account.invoice'

    def _get_move_lines(self, cr, uid, ids, to_wh, period_id,
                        pay_journal_id, writeoff_acc_id,
                        writeoff_period_id, writeoff_journal_id, date,
                        name, context=None):
        """ Function openerp is rewritten for adaptation in
        the ovl
        """
        if context is None:
            context = {}
        return []

    def ret_and_reconcile(self, cr, uid, ids, pay_amount, pay_account_id,
                          period_id, pay_journal_id, writeoff_acc_id,
                          writeoff_period_id, writeoff_journal_id, date,
                          name, to_wh, context=None):
        """ Make the payment of the invoice
        """
        if context is None:
            context = {}
        rp_obj = self.pool.get('res.partner')

        # TODO check if we can use different period for payment and the
        # writeoff line
        assert len(ids) == 1, "Can only pay one invoice at a time"
        invoice = self.browse(cr, uid, ids[0])
        src_account_id = invoice.account_id.id

        # Take the seq as name for move
        types = {'out_invoice': -1,
                 'in_invoice': 1,
                 'out_refund': 1, 'in_refund': -1}
        direction = types[invoice.type]
        l1 = {
            'debit': direction * pay_amount > 0 and direction * pay_amount,
            'credit': direction * pay_amount < 0 and - direction * pay_amount,
            'account_id': src_account_id,
            'partner_id': rp_obj._find_accounting_partner(
                invoice.partner_id).id,
            'ref': invoice.number,
            'date': date,
            'currency_id': False,
            'name': name
        }
        lines = [(0, 0, l1)]

        l2 = self._get_move_lines(
            cr, uid, ids, to_wh, period_id, pay_journal_id, writeoff_acc_id,
            writeoff_period_id, writeoff_journal_id, date,
            name, context=context)

        # TODO: check the method _get_move_lines that is forced to return []
        # and that makes that aws_customer.yml test cause a error
        if not l2:
            raise osv.except_osv(
                _('Warning !'),
                _('No accounting moves were created.\n Please, Check if there'
                  ' are Taxes/Concepts to withhold in the Invoices!'))
        lines += l2

        move = {'ref': invoice.number, 'line_id': lines,
                'journal_id': pay_journal_id, 'period_id': period_id,
                'date': date}
        move_id = self.pool.get('account.move').create(cr, uid, move,
                                                       context=context)

        self.pool.get('account.move').post(cr, uid, [move_id])

        line_ids = []
        total = 0.0
        line = self.pool.get('account.move.line')
        cr.execute(
            'select id'
            ' from account_move_line'
            ' where move_id in (' + str(move_id) + ',' +
            str(invoice.move_id.id) + ')')
        lines = line.browse(cr, uid, [item[0] for item in cr.fetchall()])
        for aml_brw in lines + invoice.payment_ids:
            if aml_brw.account_id.id == src_account_id:
                line_ids.append(aml_brw.id)
                total += (aml_brw.debit or 0.0) - (aml_brw.credit or 0.0)
        if (not round(total, self.pool.get('decimal.precision').precision_get(
                cr, uid, 'Withhold'))) or writeoff_acc_id:
            self.pool.get('account.move.line').reconcile(
                cr, uid, line_ids, 'manual', writeoff_acc_id,
                writeoff_period_id, writeoff_journal_id, context)
        else:
            self.pool.get('account.move.line').reconcile_partial(
                cr, uid, line_ids, 'manual', context)

        # Update the stored value (fields.function), so we write to trigger
        # recompute
        self.pool.get('account.invoice').write(cr, uid, ids, {},
                                               context=context)
        return {'move_id': move_id}


class AccountInvoiceTax(osv.osv):
    _inherit = 'account.invoice.tax'
    _columns = {
        'tax_id': fields.many2one(
            'account.tax', 'Tax', required=False, ondelete='set null',
            help="Tax relation to original tax, to be able to take off all"
                 " data from invoices."),
    }

    @api.model
    def compute(self, invoice):
        """ Calculate the amount, base, tax amount, base amount of the invoice
        """

        tax_grouped = {}
        if isinstance(invoice, (int, long)):
            inv = self.env['account.invoice'].browse(invoice)
        else:
            inv = invoice
        currency = inv.currency_id.with_context(
            date=inv.date_invoice or time.strftime('%Y-%m-%d'))
        company_currency = inv.company_id.currency_id
        for line in inv.invoice_line:
            for tax in line.invoice_line_tax_id.compute_all(
                    (line.price_unit * (1 - (line.discount or 0.0) / 100.0)),
                    line.quantity, line.product_id, inv.partner_id)['taxes']:
                val = {}
                val['invoice_id'] = inv.id
                val['name'] = tax['name']
                val['amount'] = tax['amount']
                val['manual'] = False
                val['sequence'] = tax['sequence']
                val['base'] = tax['price_unit'] * line['quantity']
                # add tax id #
                val['tax_id'] = tax['id']

                if inv.type in ('out_invoice', 'in_invoice'):
                    val['base_code_id'] = tax['base_code_id']
                    val['tax_code_id'] = tax['tax_code_id']
                    val['base_amount'] = currency.compute(
                        val['base'] * tax['base_sign'], company_currency,
                        round=False)
                    val['tax_amount'] = currency.compute(
                        val['amount'] * tax['tax_sign'], company_currency,
                        round=False)
                    val['account_id'] = tax['account_collected_id'] or \
                        line.account_id.id
                else:
                    val['base_code_id'] = tax['ref_base_code_id']
                    val['tax_code_id'] = tax['ref_tax_code_id']
                    val['base_amount'] = currency.compute(
                        val['base'] * tax['ref_base_sign'], company_currency,
                        round=False)
                    val['tax_amount'] = currency.compute(
                        val['amount'] * tax['ref_tax_sign'], company_currency,
                        round=False)
                    val['account_id'] = tax['account_paid_id'] or \
                        line.account_id.id

                # group by tax id #
                key = (val['tax_id'])
                if key not in tax_grouped:
                    tax_grouped[key] = val
                else:
                    tax_grouped[key]['amount'] += val['amount']
                    tax_grouped[key]['base'] += val['base']
                    tax_grouped[key]['base_amount'] += val['base_amount']
                    tax_grouped[key]['tax_amount'] += val['tax_amount']

        for tax in tax_grouped.values():
            tax['base'] = currency.round(tax['base'])
            tax['amount'] = currency.round(tax['amount'])
            tax['base_amount'] = currency.round(tax['base_amount'])
            tax['tax_amount'] = currency.round(tax['tax_amount'])
        return tax_grouped
