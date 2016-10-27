# coding: utf-8
# Copyright 2016 Vauxoo (https://www.vauxoo.com) <info@vauxoo.com>

from openerp.tests.common import TransactionCase


class TestWithholding(TransactionCase):

    def setUp(self):
        super(TestWithholding, self).setUp()
        self.so_obj = self.env['sale.order']
        self.sapi_obj = self.env['sale.advance.payment.inv']
        self.inv_obj = self.env['account.invoice']
        self.sio_obj = self.env['stock.invoice.onshipping']
        self.sale_id = self.ref('l10n_pa_withholding.so_01')
        self.sale_brw = self.so_obj.browse(self.sale_id)

    def create_invoice_from_sales_order(self, sale_id):
        sapi_brw = self.sapi_obj.create({'advance_payment_method': 'all'})
        context = {'open_invoices': True, 'active_ids': [sale_id]}
        res = sapi_brw.with_context(context).create_invoices()
        return self.inv_obj.browse(res['res_id'])

    def test_propagate_fiscal_info_from_so_to_inv(self):
        """Test that fiscal info is passed on to newly created invoice"""
        self.sale_brw.action_button_confirm()
        self.assertEquals(self.sale_brw.state, 'manual', 'Wrong State on SO')
        inv = self.create_invoice_from_sales_order(self.sale_id)
        self.assertEquals(
            inv.wh_agent_itbms, True,
            'This should be a Withholding Agent - True')
        self.assertEquals(
            inv.l10n_pa_wh_subject, 'na',
            'This should be "No Aplica" - "na"')
        return True

    def test_propagate_fiscal_info_from_so_to_inv_via_picking(self):
        """Test that fiscal info is passed on to newly created invoice when
        invoicing from picking"""

        self.sale_brw.order_policy = 'picking'
        self.sale_brw.wh_agent_itbms = False
        self.sale_brw.l10n_pa_wh_subject = '7'
        self.sale_brw.action_button_confirm()
        self.assertEquals(self.sale_brw.state, 'progress', 'Wrong State on SO')

        picking = self.sale_brw.picking_ids
        self.assertEqual(1, len(picking))
        picking.action_done()

        sio_wzd = self.sio_obj.with_context({
            'active_id': picking.id,
            'active_ids': [picking.id],
        }).create({})
        inv = self.inv_obj.browse(sio_wzd.create_invoice())
        self.assertEquals(
            inv.wh_agent_itbms, False,
            'This should not be a Withholding Agent - False')
        self.assertEquals(
            inv.l10n_pa_wh_subject, '7',
            'This should be "7"')
        return True

    def test_on_change_partner_id_on_sale_order(self):
        """Test setting null partner on Sales Order"""
        res = self.registry('sale.order').onchange_partner_id(
            self.cr, self.uid, False, False, {})
        self.assertEquals(
            res['value']['wh_agent_itbms'], False,
            'This should be a Withholding Agent - True')
        self.assertEquals(
            res['value']['l10n_pa_wh_subject'], False,
            'This should be "Empty" - "False"')
        return True
