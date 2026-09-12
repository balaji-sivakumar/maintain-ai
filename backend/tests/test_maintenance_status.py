from datetime import date

from core.maintenance_status import (
    OK,
    REPAIR_REQUESTED,
    REPLACE_REQUESTED,
    SERVICE_DUE,
    UNKNOWN,
    compute_status,
)

REFERENCE = {"service_interval_months": 12}


def test_unknown_without_reference_data():
    appliance = {"install_date": "2020-01-01"}
    assert compute_status(appliance, None, date(2026, 1, 1)) == UNKNOWN


def test_unknown_when_reference_has_no_interval():
    appliance = {"install_date": "2020-01-01"}
    assert compute_status(appliance, {}, date(2026, 1, 1)) == UNKNOWN


def test_ok_when_within_interval():
    appliance = {"install_date": "2025-06-01"}
    assert compute_status(appliance, REFERENCE, date(2026, 1, 1)) == OK


def test_service_due_when_past_interval_and_no_request_made():
    appliance = {"install_date": "2024-01-01"}
    assert compute_status(appliance, REFERENCE, date(2026, 1, 1)) == SERVICE_DUE


def test_uses_last_serviced_date_over_install_date():
    appliance = {"install_date": "2015-01-01", "last_serviced_date": "2025-08-01"}
    assert compute_status(appliance, REFERENCE, date(2026, 1, 1)) == OK


def test_repair_requested_when_due_and_repair_recorded():
    appliance = {"install_date": "2024-01-01", "requested_action": "repair"}
    assert compute_status(appliance, REFERENCE, date(2026, 1, 1)) == REPAIR_REQUESTED


def test_replace_requested_when_due_and_replace_recorded():
    appliance = {"install_date": "2024-01-01", "requested_action": "replace"}
    assert compute_status(appliance, REFERENCE, date(2026, 1, 1)) == REPLACE_REQUESTED


def test_requested_action_ignored_once_serviced_again():
    # A stale requested_action from before the appliance was actually
    # serviced shouldn't resurrect a "requested" status once it's not due.
    appliance = {
        "install_date": "2015-01-01",
        "last_serviced_date": "2025-08-01",
        "requested_action": "repair",
    }
    assert compute_status(appliance, REFERENCE, date(2026, 1, 1)) == OK
