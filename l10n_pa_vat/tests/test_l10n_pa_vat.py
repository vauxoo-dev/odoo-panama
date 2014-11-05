#!/usr/bin/python
# -*- encoding: utf-8 -*-
#
#    Module Writen to OpenERP, Open Source Management Solution
#
#    Copyright (c) 2014 Vauxoo - http://www.vauxoo.com/
#    All Rights Reserved.
#    info Vauxoo (info@vauxoo.com)
#
#    Coded by: vauxoo consultores (info@vauxoo.com)
#
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

from openerp.tests.common import TransactionCase
import traceback
import openerp.tools as tools
from openerp.osv.orm import except_orm
from openerp.tools.misc import mute_logger
import logging
_logger = logging.getLogger(__name__)


class TestVat(TransactionCase):

    def setUp(self):
        super(TestVat, self).setUp()
        self.user = self.registry('res.users')
        self.data = self.registry('ir.model.data')
        self.partner = self.registry('res.partner')

    def test_ruc_panama(self):
        cr, uid = self.cr, self.uid
        ruc_panama_to_test = {
            '00': {'valid':
                   ['PA4-444-856DV22', 'PA5-890-8976'],
                   'invalid':
                   ['PA4-444-856DV45', 'PA2-676777-98354']},
            'E': {'valid':
                  ['PAE-447-966DV09', 'PAE-790-8636'],
                  'invalid':
                  ['PAE-447-966DV75', 'PAE-I76-354']},
            'AV': {'valid':
                   ['PA5-AV-785-856DV65', 'PA7-AV-890-8976'],
                   'invalid':
                   ['PA5-AV-785-856DV23', 'PA2-676-9835474']},
            'NTJ': {'valid':
                    ['PA9-NT-787-158DV30', 'PA6-NT-730-4523'],
                    'invalid':
                    ['PA9-NT-787-158DV97', 'PA2-NY-676-98354']},
            'PE': {'valid':
                   ['PAPE-256-117DV14', 'PAPE-296-785'],
                   'invalid':
                   ['PAPE-256-117DV45', 'PAPEU-27456-117']},
            'PI': {'valid':
                   ['PA11-PI-756-249DV64', 'PA1-PI-656-439'],
                   'invalid':
                   ['PA11-PI-756-249DV56', 'PA17-PI-756-249']},
            'PAS': {'valid':
                    ['PAPAS123568966433245', 'PAPAS568575123433245'],
                    'invalid':
                    ['PAPASG', 'PAPASG12345']},
            'PJ': {'valid':
                   ['PA0102-124-563DV45', 'PA04567-756-752'],
                   'invalid':
                   ['PA0102-124-563DV77', 'PA045-G-752']},
            'NT': {'valid':
                   ['PAN1-NT-456-4445DV91', 'PAN7-NT-756-6945'],
                   'invalid':
                   ['PAN1-NT-456-4445DV22', 'PAN1-NT-478886-4452455']},
        }
        partner_test_ruc_id = self.\
            registry("ir.model.data").\
            get_object_reference(self.cr, self.uid, "l10n_pa_vat",
                                 "ruc_panama_partner_0")[1]
        for type_ruc in ruc_panama_to_test.keys():
            msg = "Testing Valid:%s and invalid: %s RUC" %\
                (ruc_panama_to_test.get(type_ruc).get('valid'),
                 ruc_panama_to_test.get(type_ruc).get('invalid'))
            _logger.info(msg)
            ruc_to_test = ruc_panama_to_test.get(type_ruc)
            print ruc_to_test, "ruc_to_testruc_to_testruc_to_testruc_to_test"
            for ruc_valid in ruc_to_test.get('valid'):
                self.partner.write(cr, uid, partner_test_ruc_id,
                                   {'vat': ruc_valid})
            for ruc_invalid in ruc_to_test.get('invalid'):
                test_ok = False
                try:
                    with mute_logger('openerp.osv.orm'):
                        self.partner.write(cr, uid, partner_test_ruc_id,
                                           {'vat':
                                            ruc_invalid})
                except except_orm:
                    error = tools.ustr(traceback.format_exc())
                    _logger.info(error)
                    test_ok = True
                assert test_ok, "Test failed."
