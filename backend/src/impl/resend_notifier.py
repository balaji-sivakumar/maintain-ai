"""Resend-backed Notifier — Day 5 deployed implementation.

Uses Resend's sandbox sender (onboarding@resend.dev), which can only deliver
to the Resend account's own signup email — fine for a single-household
hackathon demo, not something to reuse as-is for real multi-recipient use.
"""

import os
from typing import Optional

import httpx

from interfaces.notifier import Notifier

DEFAULT_FROM = "Maintain-AI <onboarding@resend.dev>"


class ResendNotifier(Notifier):
    def __init__(
        self,
        api_key: Optional[str] = None,
        to_email: Optional[str] = None,
        from_email: str = DEFAULT_FROM,
    ):
        self._api_key = api_key or os.environ.get("RESEND_API_KEY")
        self._to_email = to_email or os.environ.get("NOTIFY_EMAIL")
        self._from_email = from_email

        if not self._api_key:
            raise RuntimeError("RESEND_API_KEY is required for ResendNotifier")
        if not self._to_email:
            raise RuntimeError("NOTIFY_EMAIL is required for ResendNotifier")

    def send(self, subject: str, body: str) -> None:
        response = httpx.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {self._api_key}"},
            json={
                "from": self._from_email,
                "to": [self._to_email],
                "subject": subject,
                "text": body,
            },
            timeout=10.0,
        )
        response.raise_for_status()
