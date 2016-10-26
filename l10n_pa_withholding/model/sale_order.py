# coding: utf-8

from openerp import models, fields


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # /!\ NOTE: This code will be regarded as duplicated
    l10n_pa_wh_subject = fields.Selection([
        ('na', 'No Aplica'),
        (1, 'Pago por Servicio Profesional al Estado 100%'),
        (2, 'Pago por Venta de Bienes/Servicios al Estado 50%'),
        (3, 'Pago o Acreditacion a No Domiciliado o Empresa Constituida en el'
         ' Exterior 100%'),
        (4, 'Pago o Acreditacion por Compra de Bienes/Servicios 50%'),
        (5, 'Pago a Comercio Afiliado a Sistema de TC/TD 2%'),
        (6, 'Pago a Comercio Afiliado a Sistema de TC/TD 1%'),
        (7, 'Pago a Comercio Afiliado a Sistema de TC/TD 50%')],
        string='ITBMS Withholding Subject',
        help='If Apply. Indicates how much ITBMS to withholding on Payment')
