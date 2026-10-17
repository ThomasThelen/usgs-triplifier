from pydantic import Field

from usgs_triplifier.config import Config


class EtlConfig(Config):
    """
    Settings for the ETL pipeline
    """

    graphdb_url: str = Field(default="http://localhost:7200", alias="GRAPHDB_URL")

    # Directory GraphDB imports server files from
    graphdb_import_directory: str = Field(
        default="/root/graphdb-import/", alias="GRAPHDB_IMPORT_DIRECTORY"
    )

    graphdb_admin_username: str = Field(default="admin", alias="GDB_USER")

    # Password the ETL sets for GDB_USER
    graphdb_admin_password: str = Field(alias="GDB_PASS")

    # Password GraphDB starts with for GDB_USER, used once to set GDB_PASS
    graphdb_default_password: str = Field(default="root", alias="GDB_DEFAULT_PASS")

    # Turtle file describing the repository, used when it does not exist yet
    repository_config_path: str = Field(
        default="gnis-ld-config.ttl", alias="REPOSITORY_CONFIG"
    )
    repository_id: str = Field(default="gnis-ld", alias="REPOSITORY_ID")

    # When false, the files already in the input directory are used. Ignored
    # when LEGACY_DUMP_DATE is set; legacy dumps are never downloaded.
    download_data: bool = Field(default=True, alias="DOWNLOAD_DATA")
