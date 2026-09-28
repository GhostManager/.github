import copy
import json
import os
import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

import requests

import main
from lib.extractor import GitMetric
from main import update_repository


def traffic(day, count, uniques):
    return {
        "timestamp": f"{day}T00:00:00Z",
        "count": count,
        "uniques": uniques,
    }


class MetricsTests(unittest.TestCase):
    def test_referrers_use_window_end_and_existing_days_are_updated(self):
        stats = {
            "2026-09-25": {
                "traffic": {"count": 2, "unique": 1},
                "clones": {"count": 3, "unique": 2},
                "referrer": {"Google": {"count": 4, "unique": 3}},
            },
            "totals": {"clones": {"count": 999, "unique": 999}},
        }
        views = {"views": [traffic("2026-09-25", 4, 2), traffic("2026-09-26", 5, 3)]}
        clones = {"clones": [traffic("2026-09-25", 6, 4), traffic("2026-09-26", 7, 5)]}
        referrers = [{"referrer": "Google", "count": 10, "uniques": 8}]

        update_repository(
            stats, views, clones, referrers, [object()], date(2026, 9, 28)
        )

        self.assertNotIn("2026-09-28", stats)
        self.assertEqual(stats["2026-09-25"]["referrer"]["Google"]["count"], 4)
        self.assertEqual(stats["2026-09-26"]["referrer"]["Google"]["count"], 10)
        self.assertEqual(stats["totals"]["clones"], {"count": 13, "unique": 9})
        self.assertEqual(stats["forks"], 1)

        first_run = copy.deepcopy(stats)
        update_repository(
            stats, views, clones, referrers, [object()], date(2026, 9, 28)
        )
        self.assertEqual(stats, first_run)

    def test_lagged_window_updates_existing_day_without_creating_today(self):
        stats = {
            "2026-09-23": {
                "traffic": {"count": 2, "unique": 1},
                "clones": {"count": 3, "unique": 2},
                "referrer": {"Google": {"count": 5, "unique": 3}},
            }
        }
        views = {"views": [traffic("2026-09-23", 10, 5)]}
        clones = {"clones": [traffic("2026-09-23", 8, 4)]}
        referrers = [{"referrer": "Google", "count": 7, "uniques": 4}]

        with patch.object(main, "logger"):
            update_repository(
                stats, views, clones, referrers, [], date(2026, 9, 28)
            )

        self.assertNotIn("2026-09-28", stats)
        self.assertEqual(stats["2026-09-23"]["traffic"]["count"], 10)
        self.assertEqual(stats["2026-09-23"]["clones"]["count"], 8)
        self.assertEqual(stats["2026-09-23"]["referrer"]["Google"]["count"], 7)
        self.assertEqual(stats["totals"]["clones"], {"count": 8, "unique": 4})

    def test_mismatched_windows_do_not_change_history(self):
        stats = {}
        views = {"views": [traffic("2026-09-27", 10, 5)]}
        clones = {"clones": [traffic("2026-09-26", 8, 4)]}

        with self.assertRaisesRegex(ValueError, "do not share"):
            update_repository(stats, views, clones, [], [], date(2026, 9, 28))
        self.assertEqual(stats, {})

    def test_missing_day_in_one_response_is_rejected(self):
        stats = {}
        views = {
            "views": [traffic("2026-09-26", 3, 2), traffic("2026-09-27", 10, 5)]
        }
        clones = {"clones": [traffic("2026-09-27", 8, 4)]}

        with self.assertRaisesRegex(ValueError, "do not share"):
            update_repository(stats, views, clones, [], [], date(2026, 9, 28))
        self.assertEqual(stats, {})

    def test_future_window_is_rejected(self):
        stats = {}
        views = {"views": [traffic("2026-09-29", 10, 5)]}
        clones = {"clones": [traffic("2026-09-29", 8, 4)]}

        with self.assertRaisesRegex(ValueError, "future"):
            update_repository(stats, views, clones, [], [], date(2026, 9, 28))
        self.assertEqual(stats, {})

    def test_lagged_run_writes_available_data(self):
        with TemporaryDirectory() as directory:
            output_path = Path(directory) / "stats.json"
            original = '{"Ghostwriter": {"existing": "data"}}'
            output_path.write_text(original)
            metrics = Mock()
            metrics.get_views.return_value = {
                "views": [traffic("2026-09-23", 10, 5)]
            }
            metrics.get_clones.return_value = {
                "clones": [traffic("2026-09-23", 8, 4)]
            }
            metrics.get_referrers.return_value = []
            metrics.get_forks.return_value = []
            config = {"metrics": [{"profile": "GhostManager", "repos": ["Ghostwriter"]}]}

            with patch.object(main, "OUTPUT_PATH", output_path), patch.object(
                main, "load_config", return_value=config
            ), patch.object(main, "GitMetric", return_value=metrics), patch.object(
                main, "datetime"
            ) as clock, patch.object(main, "logger"), patch.dict(
                os.environ, {"GH_TOKEN": "unused"}
            ):
                clock.now.return_value.date.return_value = date(2026, 9, 28)
                main.main()

            saved = json.loads(output_path.read_text())["Ghostwriter"]
            self.assertEqual(saved["existing"], "data")
            self.assertEqual(saved["2026-09-23"]["traffic"]["count"], 10)
            self.assertNotIn("2026-09-28", saved)

    def test_http_error_is_not_treated_as_empty_referrers(self):
        metrics = GitMetric("GhostManager", "Ghostwriter", "unused")
        response = Mock()
        response.raise_for_status.side_effect = requests.HTTPError("403 Forbidden")

        with patch.object(metrics.session, "get", return_value=response), patch(
            "lib.extractor.logger"
        ):
            with self.assertRaises(requests.HTTPError):
                metrics.get_referrers()


if __name__ == "__main__":
    unittest.main()
