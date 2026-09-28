import json
import os
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path

from lib.extractor import GitMetric
from lib.loader import load_config
from lib.logger import logger


SCRIPT_PATH = Path(__file__).resolve().parent
CONFIG_PATH = SCRIPT_PATH / "config" / "config.yml"
OUTPUT_PATH = SCRIPT_PATH / "data" / "stats.json"
MAX_TRAFFIC_LAG_DAYS = 2


def metric_day(entry):
    """Return the UTC day assigned to a traffic API entry."""
    return date.fromisoformat(entry["timestamp"].split("T", 1)[0])


def window_end(views, clones, today):
    """Find the end of the shared 14-day traffic window."""
    view_days = [metric_day(entry) for entry in views["views"]]
    clone_days = [metric_day(entry) for entry in clones["clones"]]
    if not view_days or sorted(view_days) != sorted(clone_days):
        raise ValueError("View and clone responses do not share a traffic window")

    latest = max(view_days)
    lag_days = (today - latest).days
    if lag_days < 0:
        raise ValueError(f"GitHub traffic data is dated in the future: {latest}")
    if lag_days > MAX_TRAFFIC_LAG_DAYS:
        logger.warning(
            "GitHub traffic data ends on %s (%s days behind); merging available data",
            latest,
            lag_days,
        )
    return latest.isoformat()


def daily_entry(repo_stats, day):
    return repo_stats.setdefault(
        day,
        {
            "traffic": {"count": 0, "unique": 0},
            "clones": {"count": 0, "unique": 0},
            "referrer": {},
        },
    )


def is_day(value):
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def update_repository(repo_stats, views, clones, referrers, forks, today):
    """Merge daily metrics and one referrer snapshot into stored history."""
    as_of = window_end(views, clones, today)

    for clone in clones["clones"]:
        daily_entry(repo_stats, metric_day(clone).isoformat())["clones"] = {
            "count": clone["count"],
            "unique": clone["uniques"],
        }

    for view in views["views"]:
        daily_entry(repo_stats, metric_day(view).isoformat())["traffic"] = {
            "count": view["count"],
            "unique": view["uniques"],
        }

    # Referrers are untimestamped rolling totals. Use the traffic window's end day.
    daily_entry(repo_stats, as_of)["referrer"] = {
        ref["referrer"]: {"count": ref["count"], "unique": ref["uniques"]}
        for ref in referrers
    }
    repo_stats["forks"] = len(forks)
    totals = {"count": 0, "unique": 0}
    for day, entry in repo_stats.items():
        if is_day(day):
            totals["count"] += entry["clones"]["count"]
            totals["unique"] += entry["clones"]["unique"]
    repo_stats["totals"] = {"clones": totals}


def collect(stats_data, config, token, today):
    for project in config["metrics"]:
        owner = project["profile"]
        for repo in project["repos"]:
            metrics = GitMetric(owner, repo, token)
            views = metrics.get_views()
            clones = metrics.get_clones()
            referrers = metrics.get_referrers()
            forks = metrics.get_forks()
            update_repository(
                stats_data.setdefault(repo, {}),
                views,
                clones,
                referrers,
                forks,
                today,
            )
            logger.info("Collected traffic for %s/%s", owner, repo)
    return stats_data


def main():
    token = os.environ.get("GH_TOKEN")
    if not token:
        raise SystemExit("Set GH_TOKEN to a token with repository traffic access")

    config = load_config(CONFIG_PATH)
    with OUTPUT_PATH.open() as infile:
        stats_data = json.load(infile)

    today = datetime.now(timezone.utc).date()
    collect(stats_data, config, token, today)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", dir=OUTPUT_PATH.parent, delete=False
        ) as outfile:
            temporary_path = Path(outfile.name)
            json.dump(stats_data, outfile, indent=4)
        os.chmod(temporary_path, OUTPUT_PATH.stat().st_mode & 0o777)
        os.replace(temporary_path, OUTPUT_PATH)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
