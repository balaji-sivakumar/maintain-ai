from datetime import date

from impl.local_storage import LocalJsonStorage
from tools.appliance_tools import create_orchestrator_tools


def _make_tools(tmp_path, today=None):
    storage = LocalJsonStorage(state_path=tmp_path / "local_state.json")
    (
        add_appliance,
        lookup_maintenance_interval,
        check_due_maintenance,
        draft_service_reminder,
        log_completed_service,
        estimate_cost,
        send_notification,
    ) = create_orchestrator_tools(storage, today=today)
    return (
        storage,
        add_appliance,
        lookup_maintenance_interval,
        check_due_maintenance,
        draft_service_reminder,
        log_completed_service,
        estimate_cost,
        send_notification,
    )


def test_lookup_maintenance_interval_hit_and_miss(tmp_path):
    _, _, lookup_maintenance_interval, *_ = _make_tools(tmp_path)
    assert lookup_maintenance_interval("hvac_system")["service_interval_months"] == 12
    assert lookup_maintenance_interval("not_a_real_type") is None


def test_check_due_maintenance_silent_when_nothing_due(tmp_path):
    storage, add_appliance, _, check_due_maintenance, *_ = _make_tools(
        tmp_path, today=date(2026, 1, 1)
    )
    add_appliance("hvac_system", "Carrier", "Infinity", "2025-12-15")

    assert check_due_maintenance() == []


def test_check_due_maintenance_speaks_up_when_overdue(tmp_path):
    storage, add_appliance, _, check_due_maintenance, draft_service_reminder, *_ = _make_tools(
        tmp_path, today=date(2026, 1, 1)
    )
    add_appliance("hvac_system", "Carrier", "Infinity", "2024-01-01")  # 12mo interval, way overdue

    due = check_due_maintenance()
    assert len(due) == 1
    assert due[0]["appliance_type"] == "hvac_system"

    reminder = draft_service_reminder(due[0]["appliance_id"])
    assert "Carrier Infinity" in reminder
    assert "every 12 months" in reminder


def test_log_completed_service_clears_due_status(tmp_path):
    storage, add_appliance, _, check_due_maintenance, _, log_completed_service, *_ = _make_tools(
        tmp_path, today=date(2026, 1, 1)
    )
    appliance_id = add_appliance("hvac_system", "Carrier", "Infinity", "2024-01-01")["appliance_id"]
    assert len(check_due_maintenance()) == 1

    log_completed_service(appliance_id, "2026-01-01")

    assert check_due_maintenance() == []
    assert storage.get_appliance(appliance_id)["last_serviced_date"] == "2026-01-01"


def test_draft_service_reminder_unknown_appliance(tmp_path):
    _, _, _, _, draft_service_reminder, *_ = _make_tools(tmp_path)
    assert "No tracked appliance" in draft_service_reminder("does-not-exist")


def test_estimate_cost_unknown_appliance_short_circuits_without_calling_model(tmp_path):
    *_, estimate_cost, _ = _make_tools(tmp_path)
    assert "No tracked appliance" in estimate_cost("does-not-exist")


def test_send_notification_skips_gracefully_without_a_notifier(tmp_path):
    *_, send_notification = _make_tools(tmp_path)
    assert "skipped" in send_notification("subject", "message").lower()


def test_send_notification_calls_the_configured_notifier(tmp_path):
    storage = LocalJsonStorage(state_path=tmp_path / "local_state.json")
    sent = []

    class FakeNotifier:
        def send(self, subject, body):
            sent.append((subject, body))

    tools = create_orchestrator_tools(storage, notifier=FakeNotifier())
    send_notification = tools[-1]

    result = send_notification("Maintenance due", "Your HVAC system needs service.")

    assert sent == [("Maintenance due", "Your HVAC system needs service.")]
    assert "sent" in result.lower()
