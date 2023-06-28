import argparse
import json
import os
from datetime import datetime

from lib.extractor import GitMetric
from lib.loader import load_config
from lib.logger import logger


def dump_json(data: dict, filename: str):
    with open(filename, "w") as outfile:
        json.dump(data, outfile, indent=4)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("-t", "--token", help="GitHub Personal Access Token")
    args = parser.parse_args()

    script_path = os.path.realpath(".")
    config_path = os.path.join(script_path, "config", "config.yml")
    output_path = os.path.join(script_path, "data", "stats.json")

    config = load_config(config_path)

    with open(output_path, "r") as outfile:
        try:
            stats_data = json.load(outfile)
        except json.decoder.JSONDecodeError:
            stats_data = {}

    for project in config["metrics"]:
        owner = project["profile"]
        for repo in project["repos"]:
            if repo not in stats_data:
                stats_data[repo] = {}

            if args.token:
                token = args.token
                metrics = GitMetric(owner, repo, token)
            else:
                logger.error("Please provide a GitHub Personal Access Token with the `-t` flag")
                raise SystemExit

            today = datetime.today().strftime("%Y-%m-%d")

            views = metrics.get_views()
            view_sources = metrics.get_referrers()
            clones = metrics.get_clones()
            forks = metrics.get_forks()

            for clone in clones["clones"]:
                cur_time = datetime.strptime(clone["timestamp"].split("T")[0], "%Y-%m-%d").date().strftime("%Y-%m-%d")
                if cur_time in stats_data[repo]:
                    stats_data[repo][cur_time] = {
                        **stats_data[repo][cur_time],
                        "clones": {
                            "unique": clone["uniques"],
                            "count": clone["count"]
                        }
                    }
                else:
                    stats_data[repo][cur_time] = {
                        "clones": {
                            "unique": clone["uniques"],
                            "count": clone["count"]
                        },
                        "traffic": {
                            "count": 0,
                            "unique": 0
                        },
                        "referrer": {}
                    }

            for view in views["views"]:
                cur_time = datetime.strptime(view["timestamp"].split("T")[0], "%Y-%m-%d").date().strftime("%Y-%m-%d")
                if cur_time in stats_data[repo]:
                    stats_data[repo][cur_time] = {
                        **stats_data[repo][cur_time],
                        "traffic": {
                            "count": view["count"],
                            "unique": view["uniques"]
                        }
                    }
                else:
                    stats_data[repo][cur_time] = {
                        "traffic": {
                            "count": view["count"],
                            "unique": view["uniques"]
                        },
                        "clones": {
                            "unique": 0,
                            "count": 0
                        },
                        "referrer": {}
                    }

            referrers = {}
            for ref in view_sources:
                referrers[ref["referrer"]] = {
                    "count": ref["count"],
                    "unique": ref["uniques"]
                }
            if today in stats_data[repo]:
                stats_data[repo][today] = {
                    **stats_data[repo][today],
                    "referrer": referrers
                }
            else:
                stats_data[repo][today] = {
                    "referrer": referrers,
                    "clones": {
                        "unique": 0,
                        "count": 0,
                    },
                    "traffic": {
                        "count": 0,
                        "unique": 0,
                    },
                }

            stats_data[repo]["forks"] = len(forks)

            total_clones = 0
            total_unique_clones = 0
            for entry in stats_data[repo]:
                if entry != "forks":
                    clones = stats_data[repo][entry]["clones"]["count"]
                    uniques = stats_data[repo][entry]["clones"]["unique"]

                    total_clones += int(clones)
                    total_unique_clones += int(uniques)

            stats_data[repo]["totals"] = {
                "clones": {
                    "count": total_clones,
                    "unique": total_unique_clones
                }
            }

    dump_json(stats_data, output_path)
