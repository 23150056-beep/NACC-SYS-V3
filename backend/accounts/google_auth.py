"""Google Sign-In for staff and psychologists.

The flow: the browser gets an ID token from Google, POSTs it here, and this
module decides whether it corresponds to a real account in this system. It
never creates accounts.

That last point is the important one. This system holds child case records, so
"anyone with a Google account can sign in" is not an acceptable door. An
Administrator creates the user first — with the correct role and the person's
Google address as their email — and Google then replaces the password for that
already-authorised account. Signing in with an unknown address is rejected.
"""

import logging

from django.conf import settings
from django.utils import timezone
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from rest_framework.exceptions import AuthenticationFailed

from accounts.models import Role, User

logger = logging.getLogger(__name__)

# Google signs its ID tokens under one of these two issuer strings.
_VALID_ISSUERS = ("accounts.google.com", "https://accounts.google.com")

# Deliberately vague, and identical for "no such account", "wrong role" and
# "archived". A precise message here would let anyone with a Google account
# probe which addresses belong to agency staff.
_GENERIC_DENIAL = (
    "This Google account is not authorised for the system. Ask an "
    "Administrator to create your account first, or sign in with your "
    "email and password."
)


class GoogleAuthUnavailable(AuthenticationFailed):
    """Raised when Google Sign-In is not configured on this server."""


def verify_google_credential(credential):
    """Validate a Google ID token and return its claims.

    google-auth checks the signature against Google's rotating public keys and
    verifies audience and expiry. Anything it rejects, we reject.
    """
    client_id = settings.GOOGLE_OAUTH_CLIENT_ID
    if not client_id:
        raise GoogleAuthUnavailable(
            "Google Sign-In is not configured on this server.")
    if not credential:
        raise AuthenticationFailed("Missing Google credential.")

    try:
        claims = id_token.verify_oauth2_token(
            credential,
            google_requests.Request(),
            client_id,
            # Small tolerance for clock drift between Google and this
            # container; without it a correct token can fail near its edges.
            clock_skew_in_seconds=10,
        )
    except ValueError as exc:
        # Covers a bad signature, the wrong audience, an expired token and
        # malformed input alike — none of which the caller should be able to
        # tell apart.
        logger.warning("Rejected Google credential: %s", exc)
        raise AuthenticationFailed("Google sign-in failed. Please try again.") from exc

    if claims.get("iss") not in _VALID_ISSUERS:
        raise AuthenticationFailed("Google sign-in failed. Please try again.")

    # An unverified address proves only that someone typed it into a Google
    # account, so it must never be matched against an agency account.
    if not claims.get("email_verified"):
        raise AuthenticationFailed(
            "Your Google account's email address is not verified.")

    if not claims.get("email"):
        raise AuthenticationFailed("Google did not return an email address.")

    allowed_domains = settings.GOOGLE_ALLOWED_DOMAINS
    if allowed_domains:
        domain = claims["email"].rsplit("@", 1)[-1].lower()
        if domain not in allowed_domains:
            raise AuthenticationFailed(
                "Only agency Google accounts may sign in this way.")

    return claims


def resolve_google_user(claims):
    """Map verified Google claims onto an existing, eligible User.

    Never creates a user. Returns the User or raises AuthenticationFailed.
    """
    sub = claims["sub"]
    email = claims["email"].strip().lower()

    # Prefer the stable subject id; fall back to email only for the first
    # sign-in, when there is nothing linked yet.
    user = User.objects.filter(google_sub=sub).first()
    if user is None:
        user = User.objects.filter(email__iexact=email, google_sub__isnull=True).first()

    if user is None:
        raise AuthenticationFailed(_GENERIC_DENIAL)

    role_name = user.role.role_name if user.role else None

    # Administrators are excluded on purpose: the admin account is the
    # system's recovery path, and tying it to a third-party identity provider
    # means an outage or a lost Google account locks the agency out of its own
    # records. Admins keep password login.
    if role_name == Role.ADMINISTRATOR:
        raise AuthenticationFailed(
            "Administrator accounts sign in with email and password, not Google.")

    if role_name not in (Role.PSYCHOLOGIST, Role.STAFF):
        raise AuthenticationFailed(_GENERIC_DENIAL)

    if user.status != User.ACTIVE or not user.is_active:
        raise AuthenticationFailed(_GENERIC_DENIAL)

    return user


def link_google_account(user, claims):
    """Record the Google link on first use and return whether it was new."""
    updates = []
    newly_linked = False

    if not user.google_sub:
        user.google_sub = claims["sub"]
        updates.append("google_sub")
        newly_linked = True

    # A Google user has no password to rotate, so leaving this flag set would
    # trap them in the change-password gate with nothing to change.
    if user.must_change_password:
        user.must_change_password = False
        updates.append("must_change_password")

    user.last_login = timezone.now()
    updates.append("last_login")

    if updates:
        updates.append("updated_at")
        user.save(update_fields=updates)

    return newly_linked
