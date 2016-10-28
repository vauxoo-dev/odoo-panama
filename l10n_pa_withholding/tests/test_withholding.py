# coding: utf-8
# Copyright 2016 Vauxoo (https://www.vauxoo.com) <info@vauxoo.com>

from openerp.exceptions import except_orm
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

    def test_create_an_invoice_with_without_wh(self):
        """Test withholding in an invoice without taxes"""
        self.sale_brw.l10n_pa_wh_subject = '7'
        self.sale_brw.action_button_confirm()
        self.assertEquals(self.sale_brw.state, 'manual', 'Wrong State on SO')
        inv = self.create_invoice_from_sales_order(self.sale_id)
        inv.signal_workflow('invoice_open')
        self.assertEquals(
            inv.state, 'open', 'Wrong State on Invoice it should be "open"')
        self.assertEquals(
            bool(inv.wh_move_id), False,
            'Journal Entry for Withholding should be Empty')
        return True

    def test_create_an_invoice_with_taxes_no_wh(self):
        """Test withholding in invoice with taxes but wh_agent_itbms=False"""
        sale_id = self.ref('l10n_pa_withholding.so_02')
        sale_brw = self.so_obj.browse(sale_id)

        sale_brw.wh_agent_itbms = False
        sale_brw.action_button_confirm()

        inv = self.create_invoice_from_sales_order(sale_id)
        inv.signal_workflow('invoice_open')
        self.assertEquals(
            bool(inv.wh_move_id), False,
            'Journal Entry for Withholding should be Empty')
        return True

    def test_create_an_invoice_with_exempt_no_wh(self):
        """Test Withholding in exempt taxed invoice and wh_agent_itbms=True"""
        sale_id = self.ref('l10n_pa_withholding.so_03')
        sale_brw = self.so_obj.browse(sale_id)

        sale_brw.action_button_confirm()

        inv = self.create_invoice_from_sales_order(sale_id)
        inv.signal_workflow('invoice_open')
        self.assertEquals(
            bool(inv.wh_move_id), False,
            'Journal Entry for Withholding should be Empty')
        return True

    def test_create_an_invoice_with_taxes_wh(self):
        """Test withholding in invoice with taxes and wh_agent_itbms=True"""
        sale_id = self.ref('l10n_pa_withholding.so_02')
        sale_brw = self.so_obj.browse(sale_id)

        sale_brw.action_button_confirm()

        inv = self.create_invoice_from_sales_order(sale_id)
        inv.company_id.wh_sale_itbms_account_id = self.ref('account.iva')
        inv.signal_workflow('invoice_open')
        self.assertEquals(
            bool(inv.wh_move_id), True,
            'Journal Entry for Withholding should be Filled')
        return True

    def test_accounting_info_on_company(self):
        """Test withholding in invoice with taxes and wh_agent_itbms=True
        Missing Accounting Information on Company"""
        sale_id = self.ref('l10n_pa_withholding.so_02')
        sale_brw = self.so_obj.browse(sale_id)

        sale_brw.action_button_confirm()

        inv = self.create_invoice_from_sales_order(sale_id)

        with self.assertRaises(except_orm):
            inv.signal_workflow('invoice_open')

        return True

    def test_no_wh_subject_set(self):
        """Test withholding in invoice with taxes and wh_agent_itbms=True
        No Withholding Subject set in the Invoice"""
        sale_id = self.ref('l10n_pa_withholding.so_02')
        sale_brw = self.so_obj.browse(sale_id)

        sale_brw.action_button_confirm()

        inv = self.create_invoice_from_sales_order(sale_id)
        inv.company_id.wh_sale_itbms_account_id = self.ref('account.iva')
        inv.l10n_pa_wh_subject = False

        with self.assertRaises(except_orm):
            inv.signal_workflow('invoice_open')

        return True

    def test_create_an_exempt_invoice_with_taxes_no_wh(self):
        """Test withholding in exempt invoice with taxes and
        wh_agent_itbms=True"""
        sale_id = self.ref('l10n_pa_withholding.so_02')
        sale_brw = self.so_obj.browse(sale_id)

        sale_brw.action_button_confirm()

        inv = self.create_invoice_from_sales_order(sale_id)
        inv.l10n_pa_wh_subject = 'na'
        inv.company_id.wh_sale_itbms_account_id = self.ref('account.iva')
        inv.signal_workflow('invoice_open')
        self.assertEquals(
            bool(inv.wh_move_id), False,
            'Journal Entry for Withholding should be Empty')
        return True

    def test_already_withheld_invoice(self):
        """Test Already Withheld Invoice"""
        sale_id = self.ref('l10n_pa_withholding.so_02')
        sale_brw = self.so_obj.browse(sale_id)

        sale_brw.action_button_confirm()

        inv = self.create_invoice_from_sales_order(sale_id)
        inv.company_id.wh_sale_itbms_account_id = self.ref('account.iva')
        inv.signal_workflow('invoice_open')
        wh_move_id_1 = inv.wh_move_id.id
        inv.action_move_create_withholding()
        wh_move_id_2 = inv.wh_move_id.id
        self.assertEquals(
            wh_move_id_2, wh_move_id_1,
            'Journal Entry for Withholding should be the same')
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
