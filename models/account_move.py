import logging
from odoo import api, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = 'account.move'

    @api.model
    def create_invoice(self, header_vals, line_items):
        if not line_items:
            raise UserError('At least one line item is required.')
        resolver = self.env['invoice_api.product_resolver']
        name_cache = {}
        company_id = header_vals.get('company_id') or self.env.company.id
        lines_vals = []
        for item in line_items:
            resolved = resolver.resolve_line_item(item, name_cache, company_id)
            product = self.env['product.product'].browse(resolved['product_id'])
            line_vals = {
                'product_id': resolved['product_id'],
                'quantity': resolved.get('quantity', 1),
                'price_unit': resolved.get('price_unit') if resolved.get('price_unit') is not None else product.list_price,
                'product_uom_id': resolved['uom_id'],
            }
            if resolved.get('discount') is not None:
                line_vals['discount'] = resolved['discount']
            if resolved.get('name') or resolved.get('description'):
                line_vals['name'] = resolved.get('name') or resolved.get('description')
            lines_vals.append((0, 0, line_vals))
        move_vals = {
            'move_type': 'out_invoice',
            'partner_id': header_vals.get('partner_id'),
            'company_id': company_id,
            'invoice_line_ids': lines_vals,
        }
        if header_vals.get('journal_id'):
            move_vals['journal_id'] = header_vals['journal_id']
        if header_vals.get('invoice_date'):
            move_vals['invoice_date'] = header_vals['invoice_date']
        if header_vals.get('payment_reference'):
            move_vals['payment_reference'] = header_vals['payment_reference']
        move = self.create(move_vals)
        _logger.info('Customer invoice created via API: move_id=%s name=%s', move.id, move.name)
        return {'id': move.id, 'name': move.name}
