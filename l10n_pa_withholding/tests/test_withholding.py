# coding: utf-8
# Copyright 2016 Vauxoo (https://www.vauxoo.com) <info@vauxoo.com>

from openerp.tests.common import TransactionCase


class TestWithholding(TransactionCase):

    def setUp(self):
        super(TestWithholding, self).setUp()
        self.so_obj = self.env['sale.order']
        self.sapi_obj = self.env['sale.advance.payment.inv']
        self.inv_obj = self.env['account.invoice']
        self.sale_id = self.ref('l10n_pa_withholding.so_01')
        self.sale_brw = self.so_obj.browse(self.sale_id)

    def test_propagate_fiscal_info_from_so_to_inv(self):
        """Test that fiscal info is passed on to newly created invoice"""
        self.sale_brw.action_button_confirm()
        self.assertEquals(self.sale_brw.state, 'manual', 'Wrong State on SO')
        sapi_brw = self.sapi_obj.create({'advance_payment_method': 'all'})
        context = {'open_invoices': True, 'active_ids': [self.sale_id]}
        res = sapi_brw.with_context(context).create_invoices()
        inv = self.inv_obj.browse(res['res_id'])
        self.assertEquals(
            inv.wh_agent_itbms, True,
            'This should be a Withholding Agent - True')
        self.assertEquals(
            inv.l10n_pa_wh_subject, 'na',
            'This should be "No Aplica" - "na"')
        return True
