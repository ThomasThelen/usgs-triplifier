from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings


class Config(BaseSettings):
    # GraphDB configuration
    graphdb_host: str = Field(default="http://localhost", alias="GRAPHDB_HOST")
    graphdb_import_directory: str = Field(
        default="/root/graphdb-import/", alias="GRAPHDB_IMPORT_DIRECTORY"
    )
    graphdb_admin_username: str = Field(default="admin", alias="GDB_USER")
    graphdb_admin_password: str | None = Field(default=None, alias="GDB_PASS")
    graphdb_default_password: str = Field(default="root", alias="GDB_DEFAULT_PASS")
    repository_config_path: str = Field(
        default="gnis-ld-config.ttl", alias="REPOSITORY_CONFIG"
    )

    # Data directories
    output_directory: Path = Field(
        default=Path("/app/data/output/gnis"), alias="RDF_OUTPUT_DIRECTORY"
    )
    download_data: bool = Field(default=True, alias="DOWNLOAD_DATA")

    model_config = {"populate_by_name": True}