from usgs_triplifier.lib.dataset_downloader import DatasetDownloader
from usgs_triplifier.lib.gnis import (
    UnitsTriplifier,
    FeaturesTriplifier,
    NamesTriplifier,
    HistoryTriplifier,
)
from config import Config

from graphdb_adapter import GraphDBAdapter
import logging
import requests

logger = logging.Logger(name="ETL Logger")

logger.info("Downloading...")
DatasetDownloader.download()


logger.info("Transforming into RDF...")
for triplifier in [
    FeaturesTriplifier,
    NamesTriplifier,
    HistoryTriplifier,
    UnitsTriplifier,
]:
    triplifier()

logger.info("Configuring GraphDB")
graphdb_adapter = GraphDBAdapter()
try:
    logger.info("Enabling GraphDB security")
    graphdb_adapter.enable_security()
    logger.info("Finished enabling security")
except requests.exceptions.RequestException as security_err:
    logger.error(f"Failed to enable GraphDB security: {security_err}")

try:
    logger.info("Setting GraphDB password")
    graphdb_adapter.set_password()
    logger.info("Finished setting password")
except requests.exceptions.RequestException as pass_err:
    logger.error(f"Failed to set the GraphDB password: {pass_err}")

try:
    logger.info("Creating repository")
    graphdb_adapter.create_repository_from_config()
    logger.info("Finished creating repository")
except requests.exceptions.RequestException as new_repo_err:
    logger.error(f"Failed to create the GraphDB repository: {new_repo_err}")

try:
    logger.info("Copy triples to import directory")
    graphdb_adapter.copy_triples()
    logger.info("Finished copying triples")
except requests.exceptions.RequestException as new_repo_err:
    logger.error(f"Failed to copy triples: {new_repo_err}")

try:
    logger.info("Loading data into GraphDB")
    graphdb_adapter.load(str(Config.output_directory))
    logger.info("Finished loading data")
except requests.exceptions.RequestException as load_err:
    logger.error(f"Failed to load the data into GraphDB: {load_err}")

try:
    logger.info("Setting GraphDB permissions")
    graphdb_adapter.enable_guest_access()
    logger.info("Finished setting permissions")
except requests.exceptions.RequestException as permission_err:
    logger.error(f"Failed to set the GraphDB permissions: {permission_err}")
    