# coding: utf-8

from openerp import models, api


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    @api.model
    def _get_invoice_vals(self, key, inv_type, journal_id, move):
        res = super(StockPicking, self)._get_invoice_vals(
            key, inv_type, journal_id, move)
        if not move.picking_id.group_id:
            return res
        if not move.picking_id.group_id.procurement_ids:
            return res
        orders = [proc_brw.sale_line_id.order_id
                  for proc_brw in move.picking_id.group_id.procurement_ids
                  if proc_brw.sale_line_id]
        if not orders:
            return res
        return dict(res, wh_agent_itbms=orders[0].wh_agent_itbms,
                    l10n_pa_wh_subject=orders[0].l10n_pa_wh_subject)
