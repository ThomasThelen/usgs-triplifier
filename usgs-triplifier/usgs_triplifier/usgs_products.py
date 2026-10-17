from dataclasses import dataclass
from typing import ClassVar


@dataclass(frozen=True)
class UsgsProduct:
    """
    Represents a single USGS product (data artifact)
    """

    key: str
    pattern: str
    legacy_key: str | None = None
    legacy_pattern: str | None = None

    def pattern_for(self, legacy_dump: bool) -> str:
        """
        Returns the glob that matches the dataset's zip in the input directory.

        :param legacy_dump: Whether the input directory holds a legacy dump.
        :return: The legacy pattern for a legacy dump, otherwise the current one.
        :raises ValueError: If a legacy dump is requested for a dataset that
            legacy dumps do not include.
        """
        if not legacy_dump:
            return self.pattern
        if self.legacy_pattern is None:
            raise ValueError(f"Legacy dumps have no equivalent of {self.key}")
        return self.legacy_pattern


class UsgsProducts:
    """
    The USGS GNIS files the pipeline reads.
    """

    BUCKET: ClassVar[str] = "prd-tnm"
    S3_BASE: ClassVar[str] = f"https://{BUCKET}.s3.amazonaws.com"

    GEOPACKAGE: ClassVar[UsgsProduct] = UsgsProduct(
        key="StagedProducts/GeographicNames/FullModel/Gazetteer_National_GPKG.zip",
        pattern="*_GPKG.zip",
    )
    FEATURES: ClassVar[UsgsProduct] = UsgsProduct(
        key="StagedProducts/GeographicNames/DomesticNames/DomesticNames_National_Text.zip",
        pattern="DomesticNames*_Text.zip",
        legacy_key="StagedProducts/GeographicNames/Archive/MainDomestic/NationalFile.zip",
        legacy_pattern="NationalFile*.zip",
    )
    NAMES: ClassVar[UsgsProduct] = UsgsProduct(
        key="StagedProducts/GeographicNames/Topical/AllNames_National_Text.zip",
        pattern="AllNames*_Text.zip",
        legacy_key="StagedProducts/GeographicNames/Archive/TopicalGazetteers/AllNames.zip",
        legacy_pattern="AllNames*.zip",
    )
    UNITS: ClassVar[UsgsProduct] = UsgsProduct(
        key="StagedProducts/GeographicNames/Topical/GovernmentUnits_National_Text.zip",
        pattern="GovernmentUnits*_Text.zip",
        legacy_key="StagedProducts/GeographicNames/Archive/TopicalGazetteers/GOVT_UNITS.zip",
        legacy_pattern="GOVT_UNITS*.zip",
    )
    HISTORY: ClassVar[UsgsProduct] = UsgsProduct(
        key="StagedProducts/GeographicNames/Topical/FeatureDescriptionHistory_National_Text.zip",
        pattern="FeatureDescriptionHistory*_Text.zip",
        legacy_key="StagedProducts/GeographicNames/Archive/TopicalGazetteers/Feature_Description_History.zip",
        legacy_pattern="Feature_Description_History*.zip",
    )

    @classmethod
    def text_products(cls) -> list[UsgsProduct]:
        """
        Lists the text products.

        :return: The features, names, units and history products.
        """
        return [cls.FEATURES, cls.NAMES, cls.UNITS, cls.HISTORY]

    @classmethod
    def download_keys(cls) -> list[str]:
        """
        Lists the S3 keys of the current products, in download order.

        :return: The GeoPackage key followed by the text product keys.
        """
        return [cls.GEOPACKAGE.key, *(p.key for p in cls.text_products())]

    @classmethod
    def source_urls(cls, legacy_dump: bool) -> list[str]:
        """
        Lists the URLs of the USGS files a release is built from.

        :param legacy_dump: Whether the release is built from a legacy dump.
        :return: The legacy dump files for a legacy dump, otherwise the
            current products including the GeoPackage.
        """
        if legacy_dump:
            keys = [p.legacy_key for p in cls.text_products()]
        else:
            keys = cls.download_keys()
        return [f"{cls.S3_BASE}/{key}" for key in keys]
