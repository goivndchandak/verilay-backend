"""
Verilay — OTP Service
In-memory OTP store for MVP. Replace with Redis in production.
"""

import random
import string
from datetime import datetime, timezone, timedelta
from typing import Optional


class OTPService:
    """
    Handles OTP generation, storage, verification, and email dispatch.
    Uses an in-memory dict for MVP — swap to Redis for production.
    """

    def __init__(self):
        # In-memory store: {email: (otp_code, expiry_datetime)}
        self._otp_store: dict[str, tuple[str, datetime]] = {}

    def generate_otp(self) -> str:
        """Generate a random 6-digit OTP code."""
        return "".join(random.choices(string.digits, k=6))

    def store_otp(self, email: str) -> str:
        """
        Generate an OTP for the given email, store it with a 10-minute expiry.
        Returns the OTP code (for dev/testing — in prod, only send via email).
        """
        otp = self.generate_otp()
        expiry = datetime.now(timezone.utc) + timedelta(minutes=10)
        self._otp_store[email.lower()] = (otp, expiry)
        return otp

    def verify_otp(self, email: str, otp: str) -> bool:
        """
        Verify the OTP for a given email.
        Returns True if valid and not expired, False otherwise.
        Removes OTP from store after verification (one-time use).
        """
        key = email.lower()
        if key not in self._otp_store:
            return False

        stored_otp, expiry = self._otp_store[key]
        now = datetime.now(timezone.utc)

        if now > expiry:
            # OTP expired — clean up
            del self._otp_store[key]
            return False

        if stored_otp != otp:
            return False

        # Valid OTP — consume it
        del self._otp_store[key]
        return True

    async def send_otp_email(self, email: str, otp: str) -> None:
        """
        Send the OTP via email.
        DEV MODE: prints to console instead of sending real email.
        Replace with aiosmtplib in production.
        """
        # ── Production implementation (uncomment when ready):
        # from aiosmtplib import send
        # from email.message import EmailMessage
        # from config import get_settings
        #
        # settings = get_settings()
        # msg = EmailMessage()
        # msg["From"] = settings.OTP_EMAIL
        # msg["To"] = email
        # msg["Subject"] = "Your Verilay Verification Code"
        # msg.set_content(
        #     f"Your Verilay OTP is: {otp}\n\n"
        #     f"This code expires in 10 minutes.\n"
        #     f"If you didn't request this, please ignore."
        # )
        # await send(
        #     msg,
        #     hostname=settings.SMTP_HOST,
        #     port=settings.SMTP_PORT,
        #     start_tls=True,
        #     username=settings.OTP_EMAIL,
        #     password=settings.OTP_EMAIL_PASSWORD,
        # )

        # ── Dev mode: print to console ──
        print(f"\n{'='*50}")
        print(f"  VERILAY OTP for {email}")
        print(f"  Code: {otp}")
        print(f"  Expires in 10 minutes")
        print(f"{'='*50}\n")


# ── Singleton instance ──
otp_service = OTPService()
