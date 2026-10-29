# USGS Triplifier

The ETL process and graph database for gnis-ld.org data

- **Authors**: [Blake Regalia](https://github.com/blake-regalia), Thomas Thelen ([NCEAS](http://www.nceas.ucsb.edu))
- **License**: [Apache 2](http://opensource.org/licenses/Apache-2.0)
- [**Submit Bugs and feature requests**](https://github.com/DataONEorg/usgs-triplifier/issues)
- Contact us: support@dataone.org
- [DataONE discussions](https://github.com/DataONEorg/dataone/discussions)

## Background

The USGS hosts several data products that contain information about places: their location, name(s), descriptions, geometries, etc. These files are hosted in several formats: text, gdb, and gpkg. This repository contains an ETL 

### Retention
Before a release is validated and exported, it is compared with every earlier release in the archive, including legacy dumps added to the archive after newer releases. The record of every feature missing from the new release is copied from the newest earlier release that has it, written to the historical release file, and loaded into GraphDB. The URI of the feature keeps resolving. A retained feature is typed `usgs:HistoricalFeature` and given `gnis:lastAppearedIn <.../gnis/release/ID>` for the release it last appeared in. A feature that reappears in a later USGS product is no longer retained. A feature is a subject with a `gnis:featureId`, so a subject that only has crosswalk links is neither retained nor counted as present. The record is the feature's alias lines, its own lines, its blank nodes and its geometries. A disambiguation alias is retained only when every feature it disambiguates is missing.

### Loading
The new archive files that are produced at the end of a new run are copied to the GraphDB import directory. Next, the repository is cleared for a fresh insert. Finally, the files are imported and the loader waits for completion.

## Building releases from legacy dumps

A legacy dump is a GNIS export in the file format USGS used until 2021. USGS keeps these exports, up to 2021-08-25, under `prd-tnm/StagedProducts/GeographicNames/Archive/`. To publish one as a release:

1. Copy its zips into `GNIS_INPUT_DIRECTORY`:
   `MainDomestic/NationalFile.zip`, `TopicalGazetteers/AllNames.zip`,
   `TopicalGazetteers/Feature_Description_History.zip`, and
   `TopicalGazetteers/GOVT_UNITS.zip`.
2. Run the ETL with `LEGACY_DUMP_DATE` set to the date of the export
   (e.g. `2021-08-25`). The release is dated with that value.

The legacy file format differs from the current products in its file names, uppercase headers, two-letter state codes, and `Y`/`N` official-name flags. Legacy dumps include elevation, which is emitted as `gnis:elevation`. They have no GeoPackage, so their releases only have point geometries. The crosswalks are still harvested, and GraphDB is not reloaded.

## Developing

There are three ways to run:

1. Run the ETL directly with uv (Python 3.14), against a GraphDB at `GRAPHDB_URL`:
   `cd usgs-triplifier && GDB_PASS=<password> uv run python ../etl/code/etl.py`.
2. Run the local Docker stack, in which GraphDB is started and the ETL is run
3. Deploy with the gnis-deployment repository

The tests are run with `cd usgs-triplifier && uv run pytest`.


## Acknowledgments

Work on this package was supported by:

[![dataone_footer](https://user-images.githubusercontent.com/6643222/162324180-b5cf0f5f-ae7a-4ca6-87c3-9733a2590634.png)](http://dataone.org)

NSF OIA grant [2033521](https://www.nsf.gov/awardsearch/showAward?AWD_ID=2033521)