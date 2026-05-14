import unittest
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from jupyter_deploy.api.k8s.utils import format_age


class TestFormatAge(unittest.TestCase):
    def test_returns_empty_for_empty_string(self) -> None:
        self.assertEqual(format_age(""), "")

    def test_returns_seconds_ago(self) -> None:
        now = datetime(2025, 5, 14, 12, 0, 30, tzinfo=UTC)
        timestamp = (now - timedelta(seconds=45)).isoformat()

        with patch("jupyter_deploy.api.k8s.utils.datetime") as mock_dt:
            mock_dt.now.return_value = now
            mock_dt.fromisoformat = datetime.fromisoformat
            result = format_age(timestamp)

        self.assertEqual(result, "45s ago")

    def test_returns_minutes_ago(self) -> None:
        now = datetime(2025, 5, 14, 12, 0, 0, tzinfo=UTC)
        timestamp = (now - timedelta(minutes=15)).isoformat()

        with patch("jupyter_deploy.api.k8s.utils.datetime") as mock_dt:
            mock_dt.now.return_value = now
            mock_dt.fromisoformat = datetime.fromisoformat
            result = format_age(timestamp)

        self.assertEqual(result, "15m ago")

    def test_returns_hours_ago(self) -> None:
        now = datetime(2025, 5, 14, 12, 0, 0, tzinfo=UTC)
        timestamp = (now - timedelta(hours=3)).isoformat()

        with patch("jupyter_deploy.api.k8s.utils.datetime") as mock_dt:
            mock_dt.now.return_value = now
            mock_dt.fromisoformat = datetime.fromisoformat
            result = format_age(timestamp)

        self.assertEqual(result, "3h ago")

    def test_returns_days_ago(self) -> None:
        now = datetime(2025, 5, 14, 12, 0, 0, tzinfo=UTC)
        timestamp = (now - timedelta(days=5)).isoformat()

        with patch("jupyter_deploy.api.k8s.utils.datetime") as mock_dt:
            mock_dt.now.return_value = now
            mock_dt.fromisoformat = datetime.fromisoformat
            result = format_age(timestamp)

        self.assertEqual(result, "5d ago")

    def test_boundary_59_seconds_shows_seconds(self) -> None:
        now = datetime(2025, 5, 14, 12, 0, 0, tzinfo=UTC)
        timestamp = (now - timedelta(seconds=59)).isoformat()

        with patch("jupyter_deploy.api.k8s.utils.datetime") as mock_dt:
            mock_dt.now.return_value = now
            mock_dt.fromisoformat = datetime.fromisoformat
            result = format_age(timestamp)

        self.assertEqual(result, "59s ago")

    def test_boundary_60_seconds_shows_minutes(self) -> None:
        now = datetime(2025, 5, 14, 12, 0, 0, tzinfo=UTC)
        timestamp = (now - timedelta(seconds=60)).isoformat()

        with patch("jupyter_deploy.api.k8s.utils.datetime") as mock_dt:
            mock_dt.now.return_value = now
            mock_dt.fromisoformat = datetime.fromisoformat
            result = format_age(timestamp)

        self.assertEqual(result, "1m ago")

    def test_boundary_23_hours_shows_hours(self) -> None:
        now = datetime(2025, 5, 14, 12, 0, 0, tzinfo=UTC)
        timestamp = (now - timedelta(hours=23)).isoformat()

        with patch("jupyter_deploy.api.k8s.utils.datetime") as mock_dt:
            mock_dt.now.return_value = now
            mock_dt.fromisoformat = datetime.fromisoformat
            result = format_age(timestamp)

        self.assertEqual(result, "23h ago")

    def test_boundary_24_hours_shows_days(self) -> None:
        now = datetime(2025, 5, 14, 12, 0, 0, tzinfo=UTC)
        timestamp = (now - timedelta(hours=24)).isoformat()

        with patch("jupyter_deploy.api.k8s.utils.datetime") as mock_dt:
            mock_dt.now.return_value = now
            mock_dt.fromisoformat = datetime.fromisoformat
            result = format_age(timestamp)

        self.assertEqual(result, "1d ago")

    def test_naive_timestamp_treated_as_utc(self) -> None:
        now = datetime(2025, 5, 14, 12, 0, 0, tzinfo=UTC)
        timestamp = "2025-05-14T10:00:00"

        with patch("jupyter_deploy.api.k8s.utils.datetime") as mock_dt:
            mock_dt.now.return_value = now
            mock_dt.fromisoformat = datetime.fromisoformat
            result = format_age(timestamp)

        self.assertEqual(result, "2h ago")

    def test_invalid_timestamp_returns_original(self) -> None:
        self.assertEqual(format_age("not-a-date"), "not-a-date")

    def test_zero_seconds_shows_zero(self) -> None:
        now = datetime(2025, 5, 14, 12, 0, 0, tzinfo=UTC)
        timestamp = now.isoformat()

        with patch("jupyter_deploy.api.k8s.utils.datetime") as mock_dt:
            mock_dt.now.return_value = now
            mock_dt.fromisoformat = datetime.fromisoformat
            result = format_age(timestamp)

        self.assertEqual(result, "0s ago")
