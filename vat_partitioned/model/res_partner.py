# coding: utf-8
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

import re

from openerp import models, fields, api
from openerp.tools.translate import _


class ResPartner(models.Model):

    """ This class is inherited to add three new fields to can edit
        VAT field value """

    # Will be part of res.partner model
    _inherit = "res.partner"

    _regex_country_vat_dv = r"(?P<country>[A-Z]{2})(((?P<vatwdv>.*)"\
                            r"DV(?P<dv>.*))|(?P<vat>.*))"
    _check_country_vat_dv_re = re.compile(_regex_country_vat_dv)

    # COMPUTES AND INVERSE
    @api.one
    @api.depends('vat')
    def _get_vat_country_id(self):
        """ Get the country object from the VAT field """
        self.vat_country_id = None
        match_country_vat_dv = self._check_country_vat_dv_re.match(
            self.vat or '')
        if match_country_vat_dv:
            country_code = match_country_vat_dv.group('country')
            country_ids = self.env['res.country'].search(
                [('code', '=', country_code)],
                limit=1)
            country_id = country_ids[0].id if country_ids else None
            if country_id:
                self.vat_country_id = country_id
        elif not self.id:
            # This section process "default" case.
            company_pool = self.env['res.company']
            company_default_id = company_pool._company_default_get(
                'res.partner')
            self.vat_country_id = company_pool.browse(
                company_default_id).country_id.id

    @api.one
    @api.depends('vat')
    def _get_vat_alone(self):
        """ Get the RUC value from the VAT field """
        self.vat_alone = ""
        match_country_vat_dv = self._check_country_vat_dv_re.match(
            self.vat or '')
        if match_country_vat_dv:
            self.vat_alone = match_country_vat_dv.group('vatwdv') \
                or match_country_vat_dv.group('vat')

    @api.one
    @api.depends('vat')
    def _get_vat_dv(self):
        """ Get the DV value from the VAT field """
        self.vat_dv = ""
        match_country_vat_dv = self._check_country_vat_dv_re.match(
            self.vat or '')
        if match_country_vat_dv:
            self.vat_dv = match_country_vat_dv.group('dv')

    @api.one
    @api.depends('vat_country_id', 'vat_alone', 'vat_dv')
    def _get_new_vat(self):
        """ Get the value for VAT field through the 3 component fields """
        new_vat = ""
        if self.vat_country_id:
            new_vat += self.vat_country_id.code
        if self.vat_alone:
            new_vat += self.vat_alone
        if self.vat_dv:
            new_vat += "DV%s" % self.vat_dv
        self.vat = new_vat

    # COLUMNS (New fields)
    vat_country_id = fields.Many2one(
        'res.country', string="Country",
        ondelete="set null",
        compute='_get_vat_country_id',
        inverse='_get_new_vat',
        help=_("Country to form the TIN field"))
    vat_alone = fields.Char(
        string="RUC", size=25,
        compute='_get_vat_alone',
        inverse='_get_new_vat',
        help=_("RUC value to form the TIN field"))
    vat_dv = fields.Char(
        string="DV", size=2,
        compute='_get_vat_dv',
        inverse='_get_new_vat',
        help=_("DV value to form the TIN field"))
