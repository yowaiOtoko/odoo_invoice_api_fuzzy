from odoo import http
from odoo.http import request


class InvoiceAPIController(http.Controller):

    def _line_item_from_payload_item(self, item):
        price = item.get('price_unit', item.get('price'))
        if 'product_id' in item:
            return {'product_id': item['product_id'], 'quantity': item.get('qty', item.get('quantity', 1)), 'price_unit': price, 'price': price, 'discount': item.get('discount'), 'name': item.get('name'), 'description': item.get('description')}
        return {'product_name': item.get('name', item.get('product_name')), 'quantity': item.get('qty', item.get('quantity', 1)), 'price_unit': price, 'price': price, 'discount': item.get('discount'), 'detailed_type': item.get('detailed_type', 'service'), 'name': item.get('name'), 'description': item.get('description')}

    @http.route(
        '/api/invoice',
        type='json',
        auth='api_key',
        methods=['POST'],
        csrf=False,
    )
    def create_invoice(self, **payload):
        partner_id = payload.get('partner_id')
        items = payload.get('items', [])
        if not partner_id or not items:
            return {'error': 'Invalid payload'}
        line_items = [self._line_item_from_payload_item(it) for it in items]
        header_vals = {
            'partner_id': partner_id,
            'company_id': payload.get('company_id'),
            'journal_id': payload.get('journal_id'),
            'invoice_date': payload.get('invoice_date'),
            'payment_reference': payload.get('payment_reference'),
        }
        try:
            result = request.env['account.move'].create_invoice(header_vals, line_items)
            return {'id': result['id'], 'name': result['name'], 'invoice_id': result['id'], 'invoice_name': result['name']}
        except Exception as e:
            return {'error': str(e)}

    @http.route(
        '/api/quotation',
        type='json',
        auth='api_key',
        methods=['POST'],
        csrf=False,
    )
    def create_quotation(self, **payload):
        partner_id = payload.get('partner_id')
        items = payload.get('items', [])
        if not partner_id or not items:
            return {'error': 'Invalid payload'}
        line_items = [self._line_item_from_payload_item(it) for it in items]
        header_vals = {
            'partner_id': partner_id,
            'company_id': payload.get('company_id'),
            'validity_date': payload.get('validity_date'),
        }
        try:
            result = request.env['sale.order'].create_quotation(header_vals, line_items)
            return {'id': result['id'], 'name': result['name'], 'quotation_id': result['id'], 'quotation_name': result['name']}
        except Exception as e:
            return {'error': str(e)}
