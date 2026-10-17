import logging
import sys

from config import EtlConfig
from pipeline import Pipeline, PipelineError


def main() -> None:
    """
    Runs the pipeline with settings from the environment, logging to stdout.
    Exits with status 1 when the release cannot be published.
    """
    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stdout,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    try:
        Pipeline(EtlConfig()).run()
    except PipelineError as error:
        logging.getLogger("etl").error(str(error))
        sys.exit(1)


if __name__ == "__main__":
    main()
