"""Transactional mail for case assignment.

Restored from V2, with two deliberate changes.

**No name, no case details.** V2's email carried the child's full name and case
number in the body. Brevo is a processor outside the agency's data-processing
agreements (see the data-residency section of docs/CLOUD-DEPLOYMENT.md), and a
child's name in a third party's mail logs is exactly the disclosure that section
exists to prevent. The email now carries the case number and nothing else — the
psychologist signs in to see who it is.

**Off the request thread.** V2 called Brevo synchronously with a 20-second
timeout, inside the request that saved the child record. A slow or unreachable
Brevo would have held the save open and, on a small instance, tied up the
worker. The send now happens after the transaction commits, on a daemon thread:
the record is the source of truth and the mail must never be able to break it.
"""
import html
import json
import logging
import threading
import urllib.error
import urllib.request

from django.conf import settings
from django.db import transaction

logger = logging.getLogger(__name__)

BREVO_ENDPOINT = "https://api.brevo.com/v3/smtp/email"
_TIMEOUT = 20


def _post(payload, description):
    """POST one message to Brevo. `description` names which mail this is, and
    exists only for the log: more than one kind of message goes through here,
    and a failure that does not say which one leaves whoever is reading the
    logs looking at the wrong feature."""
    request = urllib.request.Request(
        BREVO_ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "accept": "application/json",
            "api-key": settings.BREVO_API_KEY,
            "content-type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT) as response:
            return response.status in (200, 201, 202)
    except urllib.error.HTTPError as exc:
        # Brevo says WHY in the response body, and a traceback does not carry
        # it: a rejected sender and a bad key both surface as "HTTP Error 400"
        # with nothing to tell them apart. Read the body and log it, or the
        # only honest answer to "why did no email arrive" is a guess.
        try:
            detail = exc.read().decode("utf-8", "replace")[:400]
        except Exception:                                        # noqa: BLE001
            detail = "(no response body)"
        logger.error("Brevo %s failed: HTTP %s — %s",
                     description, exc.code, detail)
        return False
    except urllib.error.URLError:
        logger.exception("Brevo %s failed: could not reach Brevo", description)
        return False
    except Exception:
        logger.exception("Unexpected error sending Brevo %s", description)
        return False


def build_payload(psychologist, case_number):
    """The message itself. Split out so a test can assert what leaves the
    building without standing up an HTTP server."""
    recipient_name = html.escape(
        getattr(psychologist, "fullname", "")
        or getattr(psychologist, "username", "")
        or "Psychologist"
    )
    return {
        "sender": {
            "name": settings.BREVO_SENDER_NAME,
            "email": settings.BREVO_SENDER_EMAIL,
        },
        "to": [{"email": psychologist.email, "name": recipient_name}],
        "subject": "New case assignment",
        "htmlContent": (
            "<h2>New case assignment</h2>"
            f"<p>Dear {recipient_name},</p>"
            "<p>A new case has been assigned to you.</p>"
            f"<p><strong>Case number:</strong> {case_number}</p>"
            "<p>Sign in to the RACCO I Child Care Management System to review it. "
            "No case details are included in this email.</p>"
            "<br><small>This is an automated notification.</small>"
        ),
    }


def send_assignment_notification(child):
    """Queue one email to the child's assigned psychologist.

    Returns True when a send was queued, False when there was nothing to send
    (no assignee, no address, no API key). Never raises — the caller is in the
    middle of saving a case record.
    """
    psychologist = getattr(child, "assigned_psychologist", None)
    if psychologist is None or not getattr(psychologist, "email", ""):
        return False
    if not settings.BREVO_API_KEY:
        logger.warning(
            "BREVO_API_KEY is not set; skipped assignment email for case %s", child.id)
        return False

    payload = build_payload(psychologist, child.id)
    # on_commit so a rolled-back save cannot send mail about a case that does
    # not exist; the thread so a slow Brevo cannot hold the response open.
    transaction.on_commit(
        lambda: threading.Thread(
            target=_post, args=(payload, "assignment email"), daemon=True).start())
    return True


def build_temporary_password_payload(user, temporary_password):
    recipient_name = html.escape(
        getattr(user, "fullname", "")
        or getattr(user, "username", "")
        or "User"
    )
    return {
        "sender": {
            "name": settings.BREVO_SENDER_NAME,
            "email": settings.BREVO_SENDER_EMAIL,
        },
        "to": [{"email": user.email, "name": recipient_name}],
        "subject": "Your NACC SYS temporary password",
        "htmlContent": (
            "<h2>Your NACC SYS account is ready</h2>"
            f"<p>Dear {recipient_name},</p>"
            "<p>An administrator created or reset your NACC SYS account.</p>"
            f"<p><strong>Temporary password:</strong> {temporary_password}</p>"
            "<p>Sign in using your email address and this password. "
            "You must change it before accessing the system.</p>"
            "<br><small>This is an automated notification.</small>"
        ),
    }


def send_temporary_password_notification(user, temporary_password):
    """Queue a temporary password email without blocking the account change.

    True means the message was handed to a background thread, NOT that it
    arrived: the Brevo call happens after this returns and its result is not
    read back. A caller that reports this to a person must say "queued", never
    "sent" — an administrator who believes an email went out is an
    administrator who does not hand the password over.
    """
    if not getattr(user, "email", ""):
        return False
    if not settings.BREVO_API_KEY:
        logger.warning(
            "BREVO_API_KEY is not set; skipped temporary password email for user %s",
            user.id)
        return False

    payload = build_temporary_password_payload(user, temporary_password)
    transaction.on_commit(
        lambda: threading.Thread(
            target=_post, args=(payload, "temporary password email"),
            daemon=True).start())
    return True
