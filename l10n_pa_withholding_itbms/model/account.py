# coding: utf-8

import time

from openerp.osv import osv
from openerp.tools.translate import _


class AccountPeriod(osv.osv):
    _inherit = "account.period"

    def _find_fortnight(self, cr, uid, date=None, context=None):
        """ This Function returns a tuple composed of
            *) period for the asked dt (int)
            *) fortnight for the asked dt (boolean):
                -) False: for the 1st. fortnight
                -) True: for the 2nd. fortnight.
            Example:
            (3,True) => a period whose id is 3 in the second fortnight
        """
        if context is None:
            context = {}
        if not date:
            date = time.strftime('%Y-%m-%d')
        period_ids = self.find(cr, uid, date, context=context)
        do = [('special', '=', False), ('id', 'in', period_ids)]
        # Due to the fact that demo data for periods sets 'special' as True on
        # them, this little hack is necesary if this issue is solved we should
        # ask directly for the refer to this bug for more information
        # https://bugs.launchpad.net/openobject-addons/+bug/924200
        demo_enabled = self.pool.get('ir.module.module').search(
            cr, uid, [('name', '=', 'base'), ('demo', '=', True)])
        domain = demo_enabled and [do[1]] or do
        # End of hack, dear future me I am really sorry for this....
        period_ids = self.search(cr, uid, domain, context=context)
        if not period_ids:
            raise osv.except_osv(
                _('Error looking Fortnight !'),
                _('There is no "Special" period defined for this date: %s.')
                % date)

        fortnight = (False if time.strptime(date, '%Y-%m-%d').tm_mday <= 15
                     else True)
        return (period_ids[0], fortnight)

    def find_fortnight(self, cr, uid, date=None, context=None):
        """
        Get the period and the fortnoght that correspond to the given dt date.
        @return a tuple( int(period_id), str(fortnight) )
        """
        # TODO: fix this workaround in version 8.0 [hbto notes]
        context = context or {}
        period, fortnight = self._find_fortnight(cr, uid, date=date,
                                                 context=context)
        return period, str(fortnight)
