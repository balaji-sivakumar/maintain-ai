"""Notifier interface — delivers reminders/recommendations to the household.

Implementations: ConsoleNotifier (local dev, no credentials needed) ->
ResendNotifier (deployed). Agent/tool code depends only on this interface.
"""

from abc import ABC, abstractmethod


class Notifier(ABC):
    @abstractmethod
    def send(self, subject: str, body: str) -> None:
        """Deliver a notification. Raises on failure — callers decide how to
        surface that (the send_notification tool reports it back to the agent)."""
