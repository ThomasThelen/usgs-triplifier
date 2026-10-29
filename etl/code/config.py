from pathlib import Path
from typing import Annotated, ClassVar

from pydantic import Field, field_validator
from pydantic_settings import NoDecode

from usgs_triplifier.config import Config


class EtlConfig(Config):
    """
    Settings for the ETL pipeline.
    """

    # Directory holding this file's parent, where gnis-ld-config.ttl is
    ETL_DIR: ClassVar[Path] = Path(__file__).resolve().parent.parent

    graphdb_url: str = Field(default="http://localhost:7200", alias="GRAPHDB_URL")

    # Directory GraphDB imports server files from
    graphdb_import_directory: str = Field(
        default="/root/graphdb-import/", alias="GRAPHDB_IMPORT_DIRECTORY"
    )

    # Seconds to wait for a server import to finish before the run fails
    graphdb_import_timeout: int = Field(
        default=4 * 60 * 60, alias="GRAPHDB_IMPORT_TIMEOUT"
    )

    # Seconds between two polls of the import status
    graphdb_import_poll: int = Field(default=30, alias="GRAPHDB_IMPORT_POLL")

    graphdb_admin_username: str = Field(default="admin", alias="GDB_USER")

    # Password the ETL sets for GDB_USER
    graphdb_admin_password: str = Field(alias="GDB_PASS")

    # Password GraphDB starts with for GDB_USER, used once to set GDB_PASS
    graphdb_default_password: str = Field(default="root", alias="GDB_DEFAULT_PASS")

    # Turtle file describing the repository, used when it does not exist yet
    repository_config_path: Path = Field(
        default=ETL_DIR / "gnis-ld-config.ttl", alias="REPOSITORY_CONFIG"
    )
    repository_id: str = Field(default="gnis-ld", alias="REPOSITORY_ID")

    # When false, the files already in the input directory are used
    download_data: bool = Field(default=True, alias="DOWNLOAD_DATA")

    # Dates (YYYY-MM-DD) of the legacy dumps that are published as releases.
    # Each one without a release file in the archive output directory is
    # built before the current release. The environment variable is a
    # comma-separated list, and an empty value disables the legacy releases.
    legacy_releases: Annotated[list[str], NoDecode] = Field(
        default=["2021-08-25"], alias="LEGACY_RELEASES"
    )

    @field_validator("legacy_releases", mode="before")
    @classmethod
    def _split_dates(cls, value: str | list[str]) -> list[str]:
        """
        Splits the comma-separated LEGACY_RELEASES value into dates.

        :param value: The environment value, or a list of dates.
        :return: The dates, without blanks.
        """
        if isinstance(value, str):
            return [date.strip() for date in value.split(",") if date.strip()]
        return value
