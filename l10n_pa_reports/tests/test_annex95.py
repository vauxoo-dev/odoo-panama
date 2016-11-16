# coding: utf-8
# Copyright 2016 Vauxoo (https://www.vauxoo.com) <info@vauxoo.com>

from openerp import fields
from openerp.tests.common import TransactionCase


class TestAccountPaAnnex95Report(TransactionCase):

    def setUp(self):
        super(TestAccountPaAnnex95Report, self).setUp()
        self.invoice_obj = self.env['account.invoice']
        self.partner_obj = self.env['res.partner']
        self.partner_id = self.partner_obj.browse(
            self.ref('l10n_pa_reports.res_partner_panama'))
        self.annex95_obj = self.env['account.pa.annex95.report']
        self.date = fields.Datetime.from_string(fields.Datetime.now())
        self.date = self.date.replace(day=1)
        if self.date.month % 12 == 0:
            self.date = self.date.replace(month=11)
        else:
            self.date = self.date.replace(month=self.date.month + 1)
        self.period_id = self.ref(
            'account.period_%s' % self.date.month)
        self.company_id = self.ref('base.main_company')
        self.date_str = fields.Datetime.to_string(self.date)
        self.inv_obj = self.env['account.invoice']
        self.invoice_id = self.inv_obj.browse(
            self.ref('l10n_pa_reports.demo_invoice_0'))
        self.invoice_id.date_invoice = fields.Datetime.to_string(self.date)
        self.filename = "Informe95_fix-ruc-on-company_%s%s.txt" % (
            self.date.year, self.date.month)

    def test_001_annex95_without_txt(self):
        """Send to generate annex95 report without movements"""
        wizard = self.annex95_obj.create({
            'period_id': self.period_id,
            'company_id': self.company_id,
        })
        wizard.create_annex95()
        self.assertFalse(wizard.file_txt, "File generated without documents.")

    def test_002_create_txt_file(self):
        """Create a txt file for Form 95"""
        self.invoice_id.signal_workflow('invoice_open')
        wizard = self.annex95_obj.create({
            'period_id': self.period_id,
            'company_id': self.company_id,
        })
        wizard.create_annex95()
        self.assertEqual(wizard.filename, self.filename)

    def test_003_partners_to_fix(self):
        """Cannot create txt because of Partners to fix Form 95"""
        self.partner_id.l10n_pa_entity = False
        self.invoice_id.signal_workflow('invoice_open')
        wizard = self.annex95_obj.create({
            'period_id': self.period_id,
            'company_id': self.company_id,
        })
        res = wizard.create_annex95()
        self.assertEqual(
            res.get('domain'),
            [('id', 'in', [self.partner_id.id])])
