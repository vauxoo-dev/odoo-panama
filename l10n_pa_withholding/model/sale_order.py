# coding: utf-8

from openerp import models, fields, api


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    wh_agent_itbms = fields.Boolean(
        string='ITBMS Withholding Agent',
        help="Indicate if the Partner is a ITBMS Withholding Agent")
    # /!\ NOTE: This code will be regarded as duplicated
    l10n_pa_wh_subject = fields.Selection([
        ('na', 'No Aplica'),
        ('1', 'Pago por Servicio Profesional al Estado 100%'),
        ('2', 'Pago por Venta de Bienes/Servicios al Estado 50%'),
        ('3', 'Pago o Acreditacion a No Domiciliado o Empresa Constituida en'
         ' el Exterior 100%'),
        ('4', 'Pago o Acreditacion por Compra de Bienes/Servicios 50%'),
        ('5', 'Pago a Comercio Afiliado a Sistema de TC/TD 2%'),
        ('6', 'Pago a Comercio Afiliado a Sistema de TC/TD 1%'),
        ('7', 'Pago a Comercio Afiliado a Sistema de TC/TD 50%')],
        string='ITBMS Withholding Subject',
        help='If Apply. Indicates how much ITBMS to withholding on Payment')

    @api.v7
    def onchange_partner_id(self, cr, uid, ids, part, context=None):
        res = super(SaleOrder, self).onchange_partner_id(
            cr, uid, ids, part, context=context)
        if not part:
            return res
        part = self.pool.get('res.partner').browse(
            cr, uid, part, context=context)
        part = part._find_accounting_partner(part)
        res['value']['wh_agent_itbms'] = part.wh_agent_itbms
        res['value']['l10n_pa_wh_subject'] = part.l10n_pa_wh_subject
        return res

    @api.model
    def _prepare_invoice(self, order, lines):
        invoice_vals = super(SaleOrder, self)._prepare_invoice(order, lines)
        return dict(invoice_vals,
                    wh_agent_itbms=order.wh_agent_itbms,
                    l10n_pa_wh_subject=order.l10n_pa_wh_subject)
