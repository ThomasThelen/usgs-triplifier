import boto3
from botocore import UNSIGNED
from botocore.config import Config as BotoConfig

from ..config import Config


class DatasetDownloader:
    def __init__(self):
        pass

    @staticmethod
    def download():
        """
        Downloads the GNIS dataset
        """
        bucket = "prd-tnm"
        key = "StagedProducts/GeographicNames/FullModel/Gazetteer_National_GPKG.zip"
        download_dir = Config.input_directory
        download_dir.mkdir(parents=True, exist_ok=True)
        local_path = download_dir / "Gazetteer_National_GPKG.zip"
        print(f"Downloading {key}...")
        s3 = boto3.client("s3", config=BotoConfig(signature_version=UNSIGNED))
        s3.download_file(bucket, key, str(local_path))
        print(f"  Saved to {local_path}")
        print("Done!")


if __name__ == "__main__":
    DatasetDownloader.download()
