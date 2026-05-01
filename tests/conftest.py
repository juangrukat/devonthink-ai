"""Shared live DEVONthink fixture UUIDs for integration tests."""

from __future__ import annotations

import os

import pytest


DB_INBOX_UUID = os.environ.get("DEVONTHINK_TEST_DATABASE_UUID", "00000000-0000-4000-8000-000000000001")
SCHOLAR_CORPUS_GROUP_UUID = os.environ.get("DEVONTHINK_TEST_SCHOLAR_GROUP_UUID", "00000000-0000-4000-8000-000000000002")
CHAOS_LAB_GROUP_UUID = os.environ.get("DEVONTHINK_TEST_CHAOS_GROUP_UUID", "00000000-0000-4000-8000-000000000003")
CHAOS_LAB_GROUP_NAME = os.environ.get("DEVONTHINK_TEST_CHAOS_GROUP_NAME", "MCP Chaos Lab Fixture")


@pytest.fixture(scope="session")
def devonthink_live_fixture_uuids() -> dict[str, str]:
    return {
        "database_inbox": DB_INBOX_UUID,
        "scholar_corpus_group": SCHOLAR_CORPUS_GROUP_UUID,
        "chaos_lab_group": CHAOS_LAB_GROUP_UUID,
        "chaos_lab_name": CHAOS_LAB_GROUP_NAME,
    }
