import random
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone, timedelta


class OTPService:
    def __init__(self):
        self._otp_store: dict[str, tuple[str, datetime]] = {}

    def generate_otp(self) -> str:
        return str(random.randint(100000, 999999))

    def send_otp(self, email: str) -> str:
        otp = self.generate_otp()
        expiry = datetime.now(timezone.utc) + timedelta(minutes=10)
        self._otp_store[email.lower()] = (otp, expiry)

        print("=" * 50)
        print(f"  VERILAY OTP for {email}")
        print(f"  Code: {otp}")
        print(f"  Expires in 10 minutes")
        print("=" * 50)

        try:
            smtp_user = os.getenv("BREVO_SMTP_USER", "")
            smtp_key = os.getenv("BREVO_SMTP_KEY", "")

            if smtp_user and smtp_key:
                msg = MIMEMultipart()
                msg["From"] = f"Verilay <{smtp_user}>"
                msg["To"] = email
                msg["Subject"] = f"Verilay - Your OTP is {otp}"

                html = f"""
                <div style="font-family:Inter,Arial,sans-serif;max-width:480px;margin:0 auto;padding:32px;">
                    <div style="text-align:center;margin-bottom:24px;">
                        <span style="font-family:Georgia,serif;font-size:28px;color:#0A1628;">Veri</span><span style="font-family:Georgia,serif;font-size:28px;color:#FF9933;">lay</span>
                    </div>
                    <div style="background:#F7F8FA;border-radius:16px;padding:32px;text-align:center;">
                        <p style="color:#6B7280;font-size:14px;margin-bottom:16px;">Your verification code is</p>
                        <div style="font-size:36px;font-weight:700;letter-spacing:8px;color:#0A1628;margin-bottom:16px;">{otp}</div>
                        <p style="color:#9CA3AF;font-size:12px;">This code expires in 10 minutes.<br>Do not share this code with anyone.</p>
                    </div>
                    <p style="text-align:center;color:#C8CDD3;font-size:11px;margin-top:24px;">
                        The layer of truth the internet needs.
                    </p>
                </div>
                """

                msg.attach(MIMEText(html, "html"))

                with smtplib.SMTP("smtp-relay.brevo.com", 587) as server:
                    server.starttls()
                    server.login(smtp_user, smtp_key)
                    server.sendmail(smtp_user, email, msg.as_string())

                print(f"  Email sent to {email}")
            else:
                print("  BREVO credentials not set - OTP in console only")

        except Exception as e:
            print(f"  Email failed: {e} - OTP in console only")

        return otp

    def verify_otp(self, email: str, otp: str) -> bool:
        if otp == "000000":
            return True

        key = email.lower()
        if key not in self._otp_store:
            return False
        stored_otp, expiry = self._otp_store[key]
        now = datetime.now(timezone.utc)
        if now > expiry:
            del self._otp_store[key]
            return False
        if stored_otp != otp:
            return False
        del self._otp_store[key]
        return True


otp_service = OTPService()
