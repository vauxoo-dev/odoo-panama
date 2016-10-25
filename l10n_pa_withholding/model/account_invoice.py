# coding: utf-8
# Copyright 2016 Vauxoo (https://www.vauxoo.com) <info@vauxoo.com>
from openerp import api, models


class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    @api.model
    def wh_tax_account(self, line):
        """Retrieves the account to use as Withholding Account"""
        return line.account_id.id

    @api.model
    def wh_move_line_get_item(self, line):
        sign = 1
        if line.invoice_id.type in ('out_invoice', 'in_invoice'):
            sign = -1
        return {
            'type': 'src',
            'name': line.name.split('\n')[0][:64],
            'account_id': self.wh_tax_account(line),
            'price': sign * line.amount,  # TODO: Insert Withheld value here!
            'tax_code_id': line.tax_code_id.id,
            'tax_amount': line.amount,
        }

    @api.model
    def wh_move_line_get(self):
        """Creates Withholding for taxes in invoice"""
        res = []
        # /!\ TODO: Invoice to be ommited for Withholding
        # return []
        # /!\ TODO: Determine if withholding will proceed because of the
        # Withholding Agent Entitlement

        if not self.tax_line:
            return []
        for tax_brw in self.tax_line:
            res.append(self.wh_move_line_get_item(tax_brw))
        return res

    @api.multi
    def compute_invoice_totals(self, company_currency, ref, iml):
        iml += self.wh_move_line_get()
        return super(AccountInvoice, self).compute_invoice_totals(
            company_currency, ref, iml)
