import logging

logging.basicConfig(
    level=logging.WARNING,
    format="%(levelname)s %(asctime)s %(message)s"
)
logger = logging.getLogger("metrics-logger")
logger.setLevel(logging.INFO)
