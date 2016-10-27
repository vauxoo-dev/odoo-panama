# coding: utf-8

from openerp import models, api


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    @api.model
    def _get_invoice_vals(self, key, inv_type, journal_id, move):
        res = super(StockPicking, self)._get_invoice_vals(
            key, inv_type, journal_id, move)
        order = move.picking_id.sale_id
        if not order:
            return res
        return dict(res, wh_agent_itbms=order.wh_agent_itbms,
                    l10n_pa_wh_subject=order.l10n_pa_wh_subject)
