import hashlib
import logging
import secrets
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SmartDocLoginToken(models.Model):
    """Single-use, expiring magic-link token that grants an Odoo web session.

    The raw token is never persisted: only its SHA-256 hash is stored, so a
    database leak does not directly expose usable tokens.
    """

    _name = 'smart_doc.login_token'
    _description = 'Magic link login token'

    token_hash = fields.Char(
        string='Token hash',
        size=64,
        required=True,
        index=True,
        copy=False,
    )
    user_id = fields.Many2one(
        'res.users',
        string='User',
        required=True,
        ondelete='cascade',
        index=True,
        copy=False,
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Partner',
        related='user_id.partner_id',
        readonly=True,
    )
    expire_on = fields.Datetime(
        string='Expires on',
        required=True,
        index=True,
        copy=False,
    )
    used_at = fields.Datetime(
        string='Used at',
        copy=False,
    )
    redirect_url = fields.Char(
        string='Redirect URL',
        copy=False,
    )
    active = fields.Boolean(
        string='Active',
        default=True,
        copy=False,
    )

    _sql_constraints = [
        ('token_hash_uniq', 'unique(token_hash)', 'Token already exists.'),
    ]

    @api.model
    def create_token(self, user_id, expires_in_hours=24, redirect_url=None):
        """Create a magic-link login token for the given user.

        :param int user_id: target ``res.users`` id (must be an internal user).
        :param int expires_in_hours: token lifetime in hours (clamped to 1..168).
        :param str|None redirect_url: optional same-host relative path to
            redirect to after login (e.g. a document deep link).
        :returns: (token_record, raw_token)
        """
        user = self.env['res.users'].browse(int(user_id)).exists()
        if not user:
            raise UserError('User not found.')
        if not user.active:
            raise UserError('User is inactive.')
        if user.share:
            raise UserError('Cannot create a login token for a portal user.')

        try:
            expires_in_hours = int(expires_in_hours)
        except (TypeError, ValueError):
            expires_in_hours = 24
        expires_in_hours = max(1, min(expires_in_hours, 168))

        raw_token = secrets.token_urlsafe(32)
        token = self.create({
            'token_hash': hashlib.sha256(raw_token.encode('utf-8')).hexdigest(),
            'user_id': user.id,
            'expire_on': fields.Datetime.now() + timedelta(hours=expires_in_hours),
            'redirect_url': redirect_url or False,
        })
        _logger.info(
            'Login token created: token_id=%s user_id=%s user_login=%s expires_in_hours=%s',
            token.id, user.id, user.login, expires_in_hours,
        )
        return token, raw_token

    def _find_by_raw(self, raw_token):
        """Look up a token record by its raw value (by SHA-256 hash), regardless of state."""
        if not raw_token:
            return self.browse()
        token_hash = hashlib.sha256(str(raw_token).encode('utf-8')).hexdigest()
        return self.sudo().search([('token_hash', '=', token_hash)], limit=1)

    def _resolve(self, raw_token):
        """Return a valid, consumable token record for ``raw_token`` or an empty recordset."""
        token = self._find_by_raw(raw_token)
        if not token:
            return token
        if not token.active:
            return self.browse()
        if token.used_at:
            return self.browse()
        if token.expire_on and token.expire_on <= fields.Datetime.now():
            return self.browse()
        if not token.user_id or not token.user_id.active:
            return self.browse()
        return token

    def _consume(self):
        self.sudo().write({'used_at': fields.Datetime.now()})
        return True

    def revoke(self, raw_token):
        """Deactivate a token by its raw value."""
        token = self._find_by_raw(raw_token)
        if not token:
            raise UserError('Token not found.')
        token.sudo().write({'active': False})
        _logger.info('Login token revoked: token_id=%s user_id=%s', token.id, token.user_id.id)
        return True
