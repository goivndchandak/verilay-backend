"""
Verilay — OTP Service
Email one-time-password generation, delivery, and verification.

Security notes:
  • No hard-coded bypass code. Every login requires a real, unexpired OTP.
  • Resend cooldown + max verify attempts guard against spamming/brute force.
  • If OTP_EMAIL_PASSWORD is configured, OTPs are emailed via SMTP; otherwise
    they are printed to the server console (local dev only).

NOTE: the OTP store is in-process memory. It is fine for a single worker, but
for multi-worker / multi-instance production deployments move this to Redis so
codes are shared across processes.
"""

import secrets
from datetime import datetime, timezone, timedelta

from config import get_settings

settings = get_settings()

OTP_TTL_MINUTES = 10
RESEND_COOLDOWN_SECONDS = 30
MAX_VERIFY_ATTEMPTS = 5


class OTPError(Exception):
    """Raised for rate-limit / cooldown violations (mapped to HTTP 429)."""
    pass


class OTPService:
    def __init__(self):
        # email -> {"otp", "expiry", "attempts", "last_sent"}
        self._store: dict[str, dict] = {}

    def generate_otp(self) -> str:
        """Cryptographically secure 6-digit code."""
        return f"{secrets.randbelow(1_000_000):06d}"

    async def send_otp(self, email: str) -> None:
        key = email.lower()
        now = datetime.now(timezone.utc)

        existing = self._store.get(key)
        if existing:
            elapsed = (now - existing["last_sent"]).total_seconds()
            if elapsed < RESEND_COOLDOWN_SECONDS:
                wait = int(RESEND_COOLDOWN_SECONDS - elapsed)
                raise OTPError(f"Please wait {wait}s before requesting another code.")

        otp = self.generate_otp()
        self._store[key] = {
            "otp": otp,
            "expiry": now + timedelta(minutes=OTP_TTL_MINUTES),
            "attempts": 0,
            "last_sent": now,
        }
        await self._deliver(email, otp)

    async def _deliver(self, email: str, otp: str) -> None:
        """Email the OTP if SMTP is configured, else print to console (dev)."""
        if settings.OTP_EMAIL_PASSWORD:
            try:
                await self._send_email(email, otp)
                return
            except Exception as e:  # fall back to console so dev isn't blocked
                print(f"[OTP] Email delivery failed ({e}); printing to console instead.")

        print("=" * 50)
        print(f"  VERILAY OTP for {email}")
        print(f"  Code: {otp}")
        print(f"  Expires in {OTP_TTL_MINUTES} minutes")
        print("=" * 50)

    async def _send_email(self, email: str, otp: str) -> None:
        import aiosmtplib
        from email.message import EmailMessage

        message = EmailMessage()
        message["From"] = settings.OTP_EMAIL
        message["To"] = email
        message["Subject"] = "Your Verilay verification code"
        message.set_content(
            f"Your Verilay verification code is {otp}.\n"
            f"It expires in {OTP_TTL_MINUTES} minutes.\n\n"
            f"If you didn't request this, you can safely ignore this email."
        )

        await aiosmtplib.send(
            message,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            start_tls=True,
            username=settings.OTP_EMAIL,
            password=settings.OTP_EMAIL_PASSWORD,
        )

    def verify_otp(self, email: str, otp: str, consume: bool = True) -> bool:
        """
        Validate an OTP.

        consume=True  → delete the OTP on success (use for the final step).
        consume=False → validate without deleting (use when you still need it,
                        e.g. verify-otp that may be followed by registration).
        """
        key = email.lower()
        record = self._store.get(key)
        if not record:
            return False

        now = datetime.now(timezone.utc)
        if now > record["expiry"]:
            self._store.pop(key, None)
            return False

        record["attempts"] += 1
        if record["attempts"] > MAX_VERIFY_ATTEMPTS:
            self._store.pop(key, None)
            return False

        if not secrets.compare_digest(record["otp"], otp):
            return False

        if consume:
            self._store.pop(key, None)
        return True

    def consume(self, email: str) -> None:
        """Explicitly invalidate an email's OTP."""
        self._store.pop(email.lower(), None)


otp_service = OTPService()
