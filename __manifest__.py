{
    'name': 'Quotations & Invoices API (products by name or id)',
    'version': '1.0.0',
    'category': 'Accounting',
    'summary': 'Create quotations and invoices via API with products by name or id, fuzzy matching',
    'author': 'yowaiotoko',
    'license': 'LGPL-3',
    'depends': [
        'account',
        'product',
        'sale',
        'web',
    ],
    'data': [
        'security/ir.model.access.csv',
    ],
    'installable': True,
    'application': False,
}
