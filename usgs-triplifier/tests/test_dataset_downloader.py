from usgs_triplifier.lib.dataset_downloader import DatasetDownloader
from usgs_triplifier.usgs_products import UsgsProducts


class FakeS3:
    """Records download_file calls instead of contacting S3."""

    def __init__(self):
        self.calls = []

    def download_file(self, bucket: str, key: str, path: str) -> None:
        """
        Records one download request.

        :param bucket: Bucket name.
        :param key: Object key.
        :param path: Local path the object would be saved to.
        """
        self.calls.append((bucket, key, path))


def test_download_fetches_gpkg_and_text_datasets(tmp_path):
    fake = FakeS3()
    download_dir = tmp_path / "input"

    paths = DatasetDownloader(download_dir, s3=fake).download()

    keys = [call[1] for call in fake.calls]
    assert keys == [
        UsgsProducts.GEOPACKAGE.key,
        UsgsProducts.FEATURES.key,
        UsgsProducts.NAMES.key,
        UsgsProducts.UNITS.key,
        UsgsProducts.HISTORY.key,
    ]
    assert all(call[0] == UsgsProducts.BUCKET for call in fake.calls)
    assert [str(p) for p in paths] == [call[2] for call in fake.calls]
    assert all(p.parent == download_dir for p in paths)
    assert download_dir.is_dir()
