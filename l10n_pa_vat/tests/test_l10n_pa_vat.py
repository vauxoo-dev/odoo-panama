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
            '00': ['PA4-444-856DV22', 'PA4-444-856DV45'],
            'E': ['PAE-447-966DV09', 'PAE-447-966DV75'],
            'AV': ['PA5-AV-785-856DV65', 'PA5-AV-785-856DV23'],
            'NTJ': ['PA9-NT-787-158DV30', 'PA9-NT-787-158DV97'],
            'PE': ['PAPE-256-117DV14', 'PAPE-256-117DV45'],
            'PI': ['PA11-PI-756-249DV64', 'PA11-PI-756-249DV56'],
            'PAS': ['PAPAS123568966433245', 'PAPASG'],
            'PJ': ['PA0102-124-563DV45', 'PA0102-124-563DV45'],
            'NT': ['PAN1-NT-456-4445DV91', 'PAN1-NT-456-4445DV22'],
        }
        partner_test_ruc_id = self.\
            registry("ir.model.data").\
            get_object_reference(self.cr, self.uid, "l10n_pa_vat",
                                 "ruc_panama_partner_0")[1]
        test_ok = False
        for type_ruc in ruc_panama_to_test.keys():
            msg = "Testing Valid:%s and invalid: %s RUC" %\
                (ruc_panama_to_test.get(type_ruc)[0],
                 ruc_panama_to_test.get(type_ruc)[1])
            _logger.info(msg)
            self.partner.write(cr, uid, partner_test_ruc_id,
                               {'vat': ruc_panama_to_test.get(type_ruc)[0]})
            try:
                with mute_logger('openerp.osv.orm'):
                    self.partner.write(cr, uid, partner_test_ruc_id,
                                       {'vat':
                                        ruc_panama_to_test.get(type_ruc)[1]})
            except except_orm:
                error = tools.ustr(traceback.format_exc())
                _logger.info(error)
                test_ok = True
            assert test_ok, "Test failed."
