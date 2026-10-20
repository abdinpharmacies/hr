import hashlib
import secrets

from odoo.http import request


def submission_owner():
    if not request.env.user._is_public():
        return hashlib.sha256(f"user:{request.env.uid}".encode()).hexdigest()
    if not request.session.get("ab_submission_owner"):
        request.session["ab_submission_owner"] = secrets.token_urlsafe(32)
    identity = f"guest:{request.session['ab_submission_owner']}"
    return hashlib.sha256(identity.encode()).hexdigest()
