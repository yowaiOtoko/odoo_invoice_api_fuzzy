import logging

from odoo import http
from odoo.http import request
from werkzeug import urls as werkzeug_urls

_logger = logging.getLogger(__name__)


class TokenLoginController(http.Controller):

    def _safe_redirect(self, url):
        """Only allow same-host relative redirect targets (open-redirect guard)."""
        if not url or not isinstance(url, str):
            return False
        if not url.startswith('/'):
            return False
        parsed = werkzeug_urls.url_parse(url)
        if parsed.scheme or parsed.netloc:
            return False
        return url

    @http.route(
        '/smart-doc/login/<string:token>',
        type='http',
        auth='public',
        methods=['GET'],
        csrf=False,
    )
    def login_by_token(self, token, **kw):
        token_record = request.env['smart_doc.login_token']._resolve(token)
        if not token_record:
            _logger.warning('Invalid, expired or already-used login token attempt')
            return request.redirect('/web/login?error=invalid_token')

        user = token_record.user_id
        # Establish a full web session for the target user without a password,
        # mirroring odoo.http.Session.finalize() (the canonical passwordless path).
        env = request.env(user=user.id)
        request.session.update({
            'db': request.db,
            'login': user.login,
            'uid': user.id,
            'context': dict(env['res.users'].context_get()),
            'session_token': env.user._compute_session_token(request.session.sid),
        })
        request.session.should_rotate = True
        request.update_env(user=user.id)
        token_record._consume()
        _logger.info(
            'Magic link login: token_id=%s user_id=%s user_login=%s',
            token_record.id, user.id, user.login,
        )

        redirect_url = self._safe_redirect(token_record.redirect_url) or '/web'
        return request.redirect(redirect_url, code=303)

    @http.route(
        '/api/token_link',
        type='jsonrpc',
        auth='api_key',
        methods=['POST'],
        csrf=False,
    )
    def create_token_link(self, **payload):
        user_id = payload.get('user_id')
        if not user_id:
            return {'error': 'Invalid payload: missing user_id'}
        redirect = payload.get('redirect')
        if redirect and not self._safe_redirect(redirect):
            return {'error': 'Invalid redirect: must be a same-host relative path'}
        expires_in = payload.get('expires_in', 24)
        try:
            token_record, raw_token = request.env['smart_doc.login_token'].create_token(
                user_id,
                expires_in_hours=expires_in,
                redirect_url=redirect,
            )
        except Exception as e:
            return {'error': str(e)}

        base_url = request.httprequest.host_url.rstrip('/')
        path = '/smart-doc/login/%s' % raw_token
        return {
            'token': raw_token,
            'path': path,
            'url': base_url + path,
            'user_id': token_record.user_id.id,
            'expires_at': token_record.expire_on.isoformat() if token_record.expire_on else None,
        }

    @http.route(
        '/api/token_link/revoke',
        type='jsonrpc',
        auth='api_key',
        methods=['POST'],
        csrf=False,
    )
    def revoke_token_link(self, **payload):
        token = payload.get('token')
        if not token:
            return {'error': 'Invalid payload: missing token'}
        try:
            request.env['smart_doc.login_token'].revoke(token)
            return {'ok': True}
        except Exception as e:
            return {'error': str(e)}
