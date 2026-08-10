import requests
import shutil
import sys
from pathlib import Path
import logging
from config import Config

logging.basicConfig(
    level=logging.INFO,
    stream=sys.stdout,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


class GraphDBAdapter:
    def __init__(self):
        self.graphdb_host = Config.graphdb_host
        self.graphdb_import_path = Path(Config.graphdb_import_directory)
        self.rdf_output_path = Config.output_directory
        self.logger = logging.getLogger("GraphDB Adapter")
        self.auth = (Config.graphdb_admin_username, Config.graphdb_admin_password)
    def load(self, rdf_output_location):
        """
        Loads data into a GraphDB repository.
        """
        self.rdf_output_path = Path(rdf_output_location)
        self.create_repository_from_config()
        self.upload()

    def set_password(self):
        """
        Set a new password for the administrator account. GraphDB comes with a default admin account
        which we authenticate with when changing the password.
        """
        response = requests.patch(
            f"{self.graphdb_host}:7200/rest/security/users/{Config.graphdb_admin_username}",
            json={
                "password": Config.graphdb_admin_password,
            },
            headers={"Content-Type": "application/json"},
            auth=(Config.graphdb_admin_username, Config.graphdb_default_password),
        )
        response.raise_for_status()
        logging.info("Set the GraphDB admin password.")

    def enable_security(self):
        """
        Enables security for GraphDB.
        """
        try:
            # First check if security is already enabled
            check_response = requests.get(
                f"{self.graphdb_host}:7200/rest/security",
                headers={"Accept": "application/json"},
            )
            if check_response.status_code == 200 and check_response.text.strip().lower() == "true":
                logging.info("GraphDB security is already enabled.")
                return

            security_response = requests.post(
                f"{self.graphdb_host}:7200/rest/security",
                json=True,
                headers={"Content-Type": "application/json", "Accept": "text/plain"},
            )
            security_response.raise_for_status()
            logging.info("Enabled GraphDB security.")
        except requests.exceptions.RequestException as error:
            logging.error(f"Failed to enable GraphDB security. {error}")
            if hasattr(error, 'response') and error.response is not None:
                logging.error(f"Response status code: {error.response.status_code}")
                logging.error(f"Response body: {error.response.text}")

    def enable_guest_access(self):
        """
        Sets the repository to use the free access security feature.
        """
        try:
            response = requests.post(
                f"{self.graphdb_host}:7200/rest/security/free-access",
                json={
                    "appSettings": {
                        "DEFAULT_SAMEAS": True,
                        "DEFAULT_INFERENCE": True,
                        "EXECUTE_COUNT": True,
                        "IGNORE_SHARED_QUERIES": False,
                    },
                    "authorities": ["READ_REPO_gnis-ld"],
                    "enabled": True,
                },
                headers={"Content-Type": "application/json"},
                auth=self.auth,
            )
            response.raise_for_status()
            logging.info("Set the 'gnis-ld' repository to read-only.")
        except requests.exceptions.RequestException as error:
            logging.error(f"Failed to make the 'gnis-ld' repository read only. {error}")
            if hasattr(error, 'response') and error.response is not None:
                logging.error(f"Response status code: {error.response.status_code}")
                logging.error(f"Response body: {error.response.text}")

    def create_repository_from_config(self):
        """
        Creates a GraphDB repository from a configuration file.
        """
        repository_config_path = Config.repository_config_path
        try:
            with open(repository_config_path, "rb") as f:
                files = {"config": f}
                response = requests.post(
                    f"{self.graphdb_host}:7200/rest/repositories",
                    files=files,
                    auth=self.auth,
                )
            response.raise_for_status()
            logging.info("Created the GraphDB repository.")
        except requests.exceptions.RequestException as error:
            if hasattr(error, 'response') and error.response is not None:
                if error.response.status_code == 400 and "already exists" in error.response.text:
                    logging.info("GraphDB repository already exists, skipping creation.")
                    return
                logging.error(f"Failed to create the GraphDB repository. {error}")
                logging.error(f"Response status code: {error.response.status_code}")
                logging.error(f"Response body: {error.response.text}")
            else:
                logging.error(f"Failed to create the GraphDB repository. {error}")

    def copy_triples(self):
        """Copies the triples that are generated to GRAPHDB_IMPORT_DIRECTORY"""
        self.graphdb_import_path.mkdir(parents=True, exist_ok=True)
        file_paths = list(self.rdf_output_path.glob("*.ttl"))

        if not file_paths:
            self.logger.warning("No triple files found to symlink")
            return []

        copied = []
        for file_path in file_paths:
            dest = self.graphdb_import_path / file_path.name
            # Remove existing file if it exists
            if dest.exists():
                dest.unlink()
            shutil.copy2(file_path, dest)
            copied.append(file_path.name)
            self.logger.info(f"Copied {file_path.name} to {dest}")

        return copied

    def upload(self):
        """
        Uploads RDF files to GraphDB.
        """
        file_paths = list(self.graphdb_import_path.glob("*.ttl"))

        if not file_paths:
            logging.info("Failed to find any triple files that should be sent to GraphDB")
            return

        file_names = [f.name for f in file_paths]

        try:
            response = requests.post(
                f"{self.graphdb_host}:7200/rest/repositories/gnis-ld/import/server",
                json={"fileNames": file_names},
                auth=self.auth,
            )
            response.raise_for_status()
            logging.info("Uploaded the triples to GraphDB.")
        except requests.RequestException as error:
            logging.error(f"There was an error uploading the triples to GraphDB: {error}")
            if hasattr(error, 'response') and error.response is not None:
                logging.error(f"Response status code: {error.response.status_code}")
                logging.error(f"Response body: {error.response.text}")
