"""
AutoSlice — Email service via Brevo SMTP relay (smtp-relay.brevo.com:587).
Uses stdlib smtplib — no extra dependencies required.
"""

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.config import settings

logger = logging.getLogger(__name__)


def send_verification_email(to_email: str, code: str, username: str) -> None:
    """Send a 6-digit email verification code via Brevo SMTP relay."""
    if not settings.smtp_user or not settings.smtp_password:
        logger.warning("[email] SMTP not configured — verification code for %s: %s", to_email, code)
        return

    plain = (
        f"Hi {username},\n\nWelcome to AutoSlice!\n\n"
        f"Your verification code is: {code}\n\n"
        f"This code expires in 15 minutes.\n\n"
        f"If you did not create an account, ignore this email.\n"
    )
    html = f"""\
<html>
  <body style="font-family:sans-serif;color:#1a1a1a;background:#f9f9f9;padding:32px;">
    <div style="max-width:480px;margin:0 auto;background:#fff;border-radius:8px;padding:32px;border:1px solid #e5e7eb;">
      <h2 style="margin-top:0;color:#1a1a1a;">Verifieer je e-mailadres</h2>
      <p>Hallo <strong>{username}</strong>, welkom bij AutoSlice!</p>
      <p>Voer de onderstaande code in om je account te activeren. De code verloopt na <strong>15 minuten</strong>.</p>
      <div style="margin:24px 0;text-align:center;">
        <span style="display:inline-block;padding:16px 40px;background:#f3f4f6;border-radius:8px;
                     font-size:36px;font-weight:700;letter-spacing:10px;color:#1a1a1a;font-family:monospace;">
          {code}
        </span>
      </div>
      <p style="color:#6b7280;font-size:13px;">Heb je geen account aangemaakt? Dan kun je deze e-mail negeren.</p>
      <hr style="border:none;border-top:1px solid #e5e7eb;margin:24px 0;">
      <p style="color:#9ca3af;font-size:12px;">AutoSlice — automatisch bericht, niet beantwoorden.</p>
    </div>
  </body>
</html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"{code} — uw AutoSlice verificatiecode"
    msg["From"]    = f"{settings.from_name} <{settings.from_email}>"
    msg["To"]      = to_email
    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
            smtp.starttls()
            smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(msg)
        logger.info("[email] Verification email sent to %s", to_email)
    except Exception:
        logger.exception("[email] Failed to send verification email to %s", to_email)


def send_password_reset_email(to_email: str, reset_link: str) -> None:
    """
    Send a password reset email via Brevo SMTP relay.
    If SMTP credentials are not configured, logs the link instead (development fallback).
    """
    if not settings.smtp_user or not settings.smtp_password:
        logger.warning("[email] SMTP credentials not set — reset link for %s: %s", to_email, reset_link)
        return

    plain = (
        f"You requested a password reset for your AutoSlice account.\n\n"
        f"Click the link below to set a new password:\n{reset_link}\n\n"
        f"This link expires in 1 hour. If you did not request this, you can ignore this email.\n"
    )

    html = f"""\
<html>
  <body style="font-family:sans-serif;color:#1a1a1a;background:#f9f9f9;padding:32px;">
    <div style="max-width:480px;margin:0 auto;background:#fff;border-radius:8px;padding:32px;border:1px solid #e5e7eb;">
      <h2 style="margin-top:0;color:#1a1a1a;">Reset your password</h2>
      <p>You requested a password reset for your <strong>AutoSlice</strong> account.</p>
      <p>Click the button below to set a new password. This link expires in <strong>1 hour</strong>.</p>
      <a href="{reset_link}"
         style="display:inline-block;margin:16px 0;padding:12px 24px;background:#e63946;color:#fff;
                text-decoration:none;border-radius:6px;font-weight:600;">
        Reset password
      </a>
      <p style="color:#6b7280;font-size:13px;">
        If you did not request this, you can safely ignore this email.
        Your password will not change.
      </p>
      <hr style="border:none;border-top:1px solid #e5e7eb;margin:24px 0;">
      <p style="color:#9ca3af;font-size:12px;">AutoSlice — automated message, do not reply.</p>
    </div>
  </body>
</html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Reset your AutoSlice password"
    msg["From"]    = f"{settings.from_name} <{settings.from_email}>"
    msg["To"]      = to_email
    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
            smtp.starttls()
            smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(msg)
        logger.info("[email] Password reset email sent to %s", to_email)
    except Exception:
        logger.exception("[email] Failed to send reset email to %s", to_email)
        # Do not raise — never reveal delivery failure to the caller
