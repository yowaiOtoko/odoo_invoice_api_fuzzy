{
    'name': 'Invoice API with Fuzzy Product Matching',
    'version': '1.0.0',
    'category': 'Accounting',
    'summary': 'Create quotations and invoices via API with products by name or id, fuzzy matching',
    'depends': [
        'account',
        'product',
        'sale',
    ],
    'data': [
        'security/ir.model.access.csv',
    ],
    'installable': True,
    'application': False,
}
