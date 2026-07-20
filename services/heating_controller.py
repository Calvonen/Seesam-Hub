from __future__ import annotations

import logging
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

logger = logging.getLogger(__name__)

HELSINKI = ZoneInfo("Europe/Helsinki")

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
SHELLY_TEST_URL = os.getenv("SHELLY_TEST_URL", "").rstrip("/")
SHELLY_TEST_CHANNEL = int(os.getenv("SHELLY_TEST_CHANNEL", "1"))


def get_today_plan() -> dict | None:
    today = datetime.now(HELSINKI).date().isoformat()

    response = requests.get(
        f"{SUPABASE_URL}/rest/v1/heating_plans",
        headers={
            "apikey": SUPABASE_ANON_KEY,
            "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
        },
        params={
            "plan_date": f"eq.{today}",
            "select": "plan_date,planned_hours,target_hours,mode,updated_at",
            "limit": "1",
        },
        timeout=10,
    )
    response.raise_for_status()

    rows = response.json()
    return rows[0] if rows else None


def get_shelly_output() -> bool:
    response = requests.get(
        f"{SHELLY_TEST_URL}/rpc/Switch.GetStatus",
        params={"id": SHELLY_TEST_CHANNEL},
        timeout=5,
    )
    response.raise_for_status()
    return bool(response.json().get("output", False))


def set_shelly_output(on: bool) -> None:
    response = requests.get(
        f"{SHELLY_TEST_URL}/rpc/Switch.Set",
        params={
            "id": SHELLY_TEST_CHANNEL,
            "on": str(on).lower(),
        },
        timeout=5,
    )
    response.raise_for_status()


def run_once() -> None:
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        raise RuntimeError("Supabase settings are missing")

    if not SHELLY_TEST_URL:
        raise RuntimeError("Shelly test URL is missing")

    now = datetime.now(HELSINKI)
    plan = get_today_plan()

    planned_hours = set(plan.get("planned_hours", [])) if plan else set()
    should_be_on = now.hour in planned_hours

    current_output = get_shelly_output()

    logger.info(
        "Heating controller: date=%s hour=%s planned=%s current=%s target=%s",
        now.date().isoformat(),
        now.hour,
        sorted(planned_hours),
        current_output,
        should_be_on,
    )

    if current_output != should_be_on:
        set_shelly_output(should_be_on)
        logger.info(
            "Shelly test channel %s set to %s",
            SHELLY_TEST_CHANNEL,
            "ON" if should_be_on else "OFF",
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_once()
