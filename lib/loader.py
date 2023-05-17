import yaml
from lib.logger import logger


def load_config(config_path) -> dict:
    """Load the config.yml file and return the contents as a dictionary."""
    logger.debug("Loading config from: %s", config_path)
    try:
        with open(config_path, "r") as yml_file:
            cfg = yaml.load(yml_file, Loader=yaml.FullLoader)
    except FileNotFoundError:
        raise SystemExit("Config file not found")

    try:
        metrics = cfg["metrics"]
        if not metrics:
            raise SystemExit("No projects defined for metrics in config")
    except KeyError:
        raise SystemExit("Metrics section not found in config")

    return cfg