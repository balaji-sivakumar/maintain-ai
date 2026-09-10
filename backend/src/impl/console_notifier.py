"""Console-log Notifier — Stage A / local-dev default, no credentials needed."""

from interfaces.notifier import Notifier


class ConsoleNotifier(Notifier):
    def send(self, subject: str, body: str) -> None:
        print(f"\n--- NOTIFICATION ---\nSubject: {subject}\n\n{body}\n--------------------\n")
