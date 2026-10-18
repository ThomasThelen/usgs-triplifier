import logging
import shutil
from pathlib import Path
from typing import ClassVar

import requests

from config import EtlConfig


class GraphDBAdapter:
    """
    Calls the GraphDB REST API to secure the server, create and clear the
    repository, and import the generated RDF files.
    """

    _log: ClassVar[logging.Logger] = logging.getLogger(__name__)

    def __init__(self, config: EtlConfig) -> None:
        """
        Creates the adapter.

        :param config: Settings holding the GraphDB URL, import directory,
            credentials and repository, and the output directory of the RDF files.
        """
        self.config = config
        self.base_url = config.graphdb_url.rstrip("/")
        self.repository_id = config.repository_id
        self.graphdb_import_path = Path(config.graphdb_import_directory)
        self.rdf_output_path = config.output_directory
        self.auth = (config.graphdb_admin_username, config.graphdb_admin_password)

    def set_password(self) -> None:
        """
        Sets the GDB_USER password to GDB_PASS. GraphDB starts with the
        password GDB_DEFAULT_PASS and keeps its home directory between runs,
        so the password is only changed when GraphDB does not already accept
        GDB_PASS.

        :raises requests.HTTPError: If GraphDB rejects the password change.
        """
        user_url = (
            f"{self.base_url}/rest/security/users/{self.config.graphdb_admin_username}"
        )
        if requests.get(user_url, auth=self.auth).status_code == 200:
            self._log.info("The GraphDB admin password is already set.")
            return

        response = requests.patch(
            user_url,
            json={"password": self.config.graphdb_admin_password},
            headers={"Content-Type": "application/json"},
            auth=(
                self.config.graphdb_admin_username,
                self.config.graphdb_default_password,
            ),
        )
        response.raise_for_status()
        self._log.info("The GraphDB admin password was set.")

    def enable_security(self) -> None:
        """
        Turns on GraphDB security, unless GraphDB reports it is already on.

        :raises requests.HTTPError: If GraphDB rejects the request.
        """
        check_response = requests.get(
            f"{self.base_url}/rest/security",
            headers={"Accept": "application/json"},
        )
        if (
            check_response.status_code == 200
            and check_response.text.strip().lower() == "true"
        ):
            self._log.info("GraphDB security is already enabled.")
            return

        response = requests.post(
            f"{self.base_url}/rest/security",
            json=True,
            headers={"Content-Type": "application/json", "Accept": "text/plain"},
        )
        response.raise_for_status()
        self._log.info("Enabled GraphDB security.")

    def enable_guest_access(self) -> None:
        """
        Turns on GraphDB free access.

        :raises requests.HTTPError: If GraphDB rejects the request.
        """
        response = requests.post(
            f"{self.base_url}/rest/security/free-access",
            json={
                "appSettings": {
                    "DEFAULT_SAMEAS": True,
                    "DEFAULT_INFERENCE": True,
                    "EXECUTE_COUNT": True,
                    "IGNORE_SHARED_QUERIES": False,
                },
                "authorities": [f"READ_REPO_{self.repository_id}"],
                "enabled": True,
            },
            headers={"Content-Type": "application/json"},
            auth=self.auth,
        )
        response.raise_for_status()
        self._log.info(
            f"Granted anonymous read access to the '{self.repository_id}' repository."
        )

    def create_repository_from_config(self) -> None:
        """
        Creates the repository from the Turtle file at REPOSITORY_CONFIG.
        Does nothing if the repository already exists.

        :raises FileNotFoundError: If the REPOSITORY_CONFIG file does not exist.
        :raises requests.HTTPError: If GraphDB rejects the request.
        """
        check_response = requests.get(
            f"{self.base_url}/rest/repositories/{self.repository_id}",
            headers={"Accept": "application/json"},
            auth=self.auth,
        )
        if check_response.status_code == 200:
            self._log.info("GraphDB repository already exists, skipping creation.")
            return

        with open(self.config.repository_config_path, "rb") as f:
            response = requests.post(
                f"{self.base_url}/rest/repositories",
                files={"config": f},
                auth=self.auth,
            )
        response.raise_for_status()
        self._log.info("Created the GraphDB repository.")

    def clear_repository(self) -> None:
        """
        Removes every statement from the repository.

        :raises requests.HTTPError: If GraphDB rejects the request.
        """
        response = requests.delete(
            f"{self.base_url}/repositories/{self.repository_id}/statements",
            auth=self.auth,
        )
        response.raise_for_status()
        self._log.info("Cleared the previous release from the repository.")

    def copy_triples(self) -> list[str]:
        """
        Replaces the .nt.gz and .ttl files in the GraphDB import directory
        with the ones in the output directory.

        :return: Names of the copied files; empty when the output directory has none.
        """
        self.graphdb_import_path.mkdir(parents=True, exist_ok=True)

        for pattern in ("*.nt.gz", "*.ttl"):
            for stale in self.graphdb_import_path.glob(pattern):
                stale.unlink()

        file_paths = list(self.rdf_output_path.glob("*.nt.gz")) + list(
            self.rdf_output_path.glob("*.ttl")
        )

        if not file_paths:
            self._log.warning("No triple files found to copy")
            return []

        copied = []
        for file_path in file_paths:
            dest = self.graphdb_import_path / file_path.name
            shutil.copy2(file_path, dest)
            copied.append(file_path.name)
            self._log.info(f"Copied {file_path.name} to {dest}")

        return copied

    def start_import(self) -> None:
        """
        Starts a GraphDB server import of every .nt.gz and .ttl file in the
        import directory into the repository.

        :raises requests.HTTPError: If GraphDB rejects the request.
        """
        file_paths = list(self.graphdb_import_path.glob("*.nt.gz")) + list(
            self.graphdb_import_path.glob("*.ttl")
        )

        if not file_paths:
            self._log.warning("No triple files in the import directory to import")
            return

        response = requests.post(
            f"{self.base_url}/rest/repositories/{self.repository_id}/import/server",
            json={"fileNames": [f.name for f in file_paths]},
            auth=self.auth,
        )
        response.raise_for_status()
        self._log.info(f"Started the GraphDB import of {len(file_paths)} files.")
