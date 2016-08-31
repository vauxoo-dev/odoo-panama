# coding: utf-8

from openerp import models, fields, api, exceptions, _


class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    def _get_move_lines(self, cr, uid, ids, to_wh, period_id,
                        pay_journal_id, writeoff_acc_id,
                        writeoff_period_id, writeoff_journal_id, date,
                        name, context=None):
        """ Function openerp is rewritten for adaptation in the ovl """
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
            raise exceptions.except_orm(
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


class AccountInvoiceTax(models.Model):
    _inherit = 'account.invoice.tax'

    tax_id = fields.Many2one(
        'account.tax', 'Tax', required=False, ondelete='set null',
        help="Tax relation to original tax, to be able to take off all"
        " data from invoices.")

    @api.model
    def compute(self, invoice):
        """ Inserts account.tax `id` in account.invoice.tax records
        """

        tax_grouped = super(AccountInvoiceTax, self).compute(invoice)
        at_obj = self.env['account.tax']

        for tax_key, tax_val in tax_grouped.iteritems():
            tax_args = [('name', '=', tax_val['name'])]
            if invoice.type in ('out_invoice', 'in_invoice'):
                tax_args += [
                    ('tax_code_id', '=', tax_key[0]),
                    ('base_code_id', '=', tax_key[1])]
            else:
                tax_args += [
                    ('ref_tax_code_id', '=', tax_key[0]),
                    ('ref_base_code_id', '=', tax_key[1])]

            at_id = at_obj.search(tax_args, limit=1)
            if not at_id:
                continue
            tax_grouped[tax_key]['tax_id'] = at_id.id

        return tax_grouped
