from odoo import models
from odoo.exceptions import AccessDenied
from odoo.http import request


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    @classmethod
    def _auth_method_api_key(cls):
        api_key = request.httprequest.headers.get('API-KEY') or request.httprequest.environ.get('HTTP_API_KEY')
        if not api_key:
            raise AccessDenied()
        uid = request.env['res.users.apikeys']._check_credentials(scope='rpc', key=api_key)
        if not uid:
            raise AccessDenied()
        request.update_env(user=uid)
        return True
