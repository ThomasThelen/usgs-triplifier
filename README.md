# USGS Triplifier

The ETL process and graph database for gnis-ld.org data

- **Authors**: [Blake Regalia](https://github.com/blake-regalia), Thomas Thelen ([NCEAS](http://www.nceas.ucsb.edu))
- **License**: [Apache 2](http://opensource.org/licenses/Apache-2.0)
- [**Submit Bugs and feature requests**](https://github.com/DataONEorg/usgs-triplifier/issues)
- Contact us: support@dataone.org
- [DataONE discussions](https://github.com/DataONEorg/dataone/discussions)

## Background

The USGS hosts several data products that contain information about places: their location, name(s), descriptions, geometries, etc. These files are hosted in several formats: text, gdb, and gpkg. This repository contains

1. A python library for converting the names database to RDF.
2. A graph database service for hosting the data
3. An ETL process for fetching the data from USGS, transforming it into RDF, and loading it into the graph database

## Releases and the archive

Every ETL run publishes a new release into the archive directory
(`ARCHIVE_OUTPUT_DIRECTORY`):

| File | What it is |
|---|---|
| `gnis-ld-<YYMMDD>.nt.gz` | The release file (gzipped N-Triples) |
| `gnis-ld-<YYMMDD>.meta.json` | Sidecar with the display fields the website reads: `id`, `published`, `triples`, `size` |
| `gnis-ld-historical-<YYMMDD>.nt.gz` (+ sidecar) | The historical release file with the records retained for features dropped upstream |
| `ontologies/gnis.ttl`, `ontologies/usgs.ttl` | The two ontologies, from `usgs_triplifier/ontologies/`, with the base IRI of this deployment. Each release file also contains them as N-Triples, and GraphDB loads them with the data |

These files are used by gnis-ld.org, which scans the volume mount and derives its downloads page, `releases.json` manifest, and VoID release records from the filenames and sidecars.

### Retention
After a release is exported, it is compared with every earlier release in the archive, including legacy dumps added later. The records of every subject missing from the new release are copied from the newest earlier release that has them, written to the historical release file, and loaded into GraphDB, so their URIs keep resolving. Each such feature is typed `usgs:HistoricalFeature` and given `gnis:lastAppearedIn <.../gnis/release/ID>` for that release. A feature that reappears upstream leaves the historical set.

### Loading
Each run copies the release files to the GraphDB import directory, clears the repository, imports the files and waits for the import to finish.

## Building releases from legacy dumps

A legacy dump is a GNIS export in the file format USGS used until 2021. USGS keeps these exports, up to 2021-08-25, under `prd-tnm/StagedProducts/GeographicNames/Archive/`. To publish one as a release:

1. Copy its zips into `GNIS_INPUT_DIRECTORY`:
   `MainDomestic/NationalFile.zip`, `TopicalGazetteers/AllNames.zip`,
   `TopicalGazetteers/Feature_Description_History.zip`, and
   `TopicalGazetteers/GOVT_UNITS.zip`.
2. Run the ETL with `LEGACY_DUMP_DATE` set to the date of the export
   (e.g. `2021-08-25`). The release is dated with that value.

The legacy file format differs from the current products in its file names, uppercase headers, two-letter state codes, and `Y`/`N` official-name flags. Legacy dumps include elevation, which is emitted as `gnis:elevation`. They have no GeoPackage, so their releases only have point geometries. The crosswalks are still harvested, and GraphDB is not reloaded.

## Configuration

| Variable | Purpose |
|---|---|
| `LOD_BASE` / `GEO_BASE` | Base URIs minted into every triple |
| `GNIS_INPUT_DIRECTORY` / `RDF_OUTPUT_DIRECTORY` | Where source zips are read and generated `.nt.gz` files are written |
| `ARCHIVE_OUTPUT_DIRECTORY` | Where the release files are written |
| `SITE_BASE` | Public website base used for download URLs in the dataset metadata |
| `DOWNLOAD_DATA` | Set `false` to reuse already-downloaded inputs |
| `LEGACY_DUMP_DATE` | Build the release from the legacy dump with this date |
| `RELEASE_DATE` | Date to put on the release instead of the time of the run |
| `GRAPHDB_URL` | GraphDB the release is loaded into |
| `GDB_USER` / `GDB_PASS` / `GDB_DEFAULT_PASS` | Admin user, the password the ETL sets for it, and the password GraphDB starts with |
| `GRAPHDB_IMPORT_DIRECTORY` | Directory GraphDB imports server files from |
| `GRAPHDB_IMPORT_TIMEOUT` / `GRAPHDB_IMPORT_POLL` | How long the ETL waits for the import to finish, and how often it checks |
| `REPOSITORY_ID` / `REPOSITORY_CONFIG` | Repository name and the Turtle file it is created from (`etl/gnis-ld-config.ttl`) |


## Developing

There are three ways to run:

1. Run the ETL directly with uv (Python 3.14), against a GraphDB at `GRAPHDB_URL`:
   `cd usgs-triplifier && GDB_PASS=<password> uv run python ../etl/code/etl.py`.
   The settings are read from the environment variables in the table above.
2. Run the local Docker stack, which starts GraphDB and runs the ETL
3. Deploy with the gnis-deployment repository

The tests run with `cd usgs-triplifier && uv run pytest`.


## Acknowledgments

Work on this package was supported by:

[![dataone_footer](https://user-images.githubusercontent.com/6643222/162324180-b5cf0f5f-ae7a-4ca6-87c3-9733a2590634.png)](http://dataone.org)

NSF OIA grant [2033521](https://www.nsf.gov/awardsearch/showAward?AWD_ID=2033521)