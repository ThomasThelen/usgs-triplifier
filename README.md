# USGS Triplifier

The ETL process and graph database for gnis-ld.org data

- **Authors**: [Blake Regalia](https://github.com/blake-regalia), Thomas Thelen ([NCEAS](http://www.nceas.ucsb.edu))
- **License**: [Apache 2](http://opensource.org/licenses/Apache-2.0)
- [**Submit Bugs and feature requests**](https://github.com/DataONEorg/usgs-triplifier/issues)
- Contact us: support@dataone.org
- [DataONE discussions](https://github.com/DataONEorg/dataone/discussions)

## Background

The USGS hosts several data products that contain information about places: their location, name(s), descriptions, geometries, etc. These files are hosted in several formats: text, gdb, and gpkg. This repository contains

1. A python library for converting the names database in the gpkg data format to RDF
2. A graph database service for hosting the data
3. An ETL process for fetching the data from USGS, transforming it into RDF, and loading it into the graph database

## Releases and the archive

Every ETL run publishes a new release into the archive directory
(`ARCHIVE_OUTPUT_DIRECTORY`):

| File | What it is |
|---|---|
| `gnis-ld-<YYMMDD>.nt.gz` | The full release dump (gzipped N-Triples) |
| `gnis-ld-<YYMMDD>.meta.json` | Sidecar with the display fields the website reads: `id`, `published`, `triples`, `size` |
| `gnis-ld-historical-<YYMMDD>.nt.gz` (+ sidecar) | Companion dump of records retained for features dropped upstream |

These files are used by gnis-ld.org, which scans the volume mount and derives its downloads page, `releases.json` manifest, and VoID release records from the filenames and sidecars.

Two behaviors to know about:

- **Retention.** Feature URIs are permanent. Before each release the pipeline diffs the new dump against the previous release. Any record that was removed from the new release upstream is still carried forward and typed as `usgs:HistoricalFeature`. The feature is also annotated with `gnis:lastAppearedIn <.../gnis/release/ID>`, so its URI keeps resolving. A feature that reappears upstream leaves the historical set.

- **Full replacement.** Each load clears the repository and reloads it, so stale values never accumulate. The dataset metadata re-describes every archived release on every build, which is how the release lineage stays queryable across reloads.

## Backfilling from legacy data

USGS keeps its pre-GPKG file archive (through 2021-08-25) under `prd-tnm/StagedProducts/GeographicNames/Archive/`. To publish one of these as a release:

1. Stage the archived zips in `GNIS_INPUT_DIRECTORY`:
   `MainDomestic/NationalFile.zip`, `TopicalGazetteers/AllNames.zip`,
   `TopicalGazetteers/Feature_Description_History.zip`, and
   `TopicalGazetteers/GOVT_UNITS.zip`.
2. Run the ETL with `ARCHIVE_MODE=true` and `RELEASE_DATE=<vintage date>`
   (e.g. `2021-08-25`).

In archive mode the pipeline reads the old pipe-delimited formats(uppercase headers, two-letter state codes, `Y`/`N` official-name flags), emits `gnis:elevation` (which only the old vintages carry), and still harvests the crosswalks.

## Configuration

| Variable | Purpose |
|---|---|
| `LOD_BASE` / `GEO_BASE` | Base URIs minted into every triple |
| `GNIS_INPUT_DIRECTORY` / `RDF_OUTPUT_DIRECTORY` | Where source zips are read and generated `.nt.gz` files are written |
| `ARCHIVE_OUTPUT_DIRECTORY` | Where release dumps are published |
| `SITE_BASE` | Public website base used for download URLs in the dataset metadata |
| `DOWNLOAD_DATA` | Set `false` to reuse already-downloaded inputs |
| `ARCHIVE_MODE` / `RELEASE_DATE` | Backfill an archived vintage |


## Developing

There are three ways to run:

1. Directly calling the ugs-triplifier package via `python -m <one of the modules here>`
2. By running the local docker stack and letting automation download, triplify, and upload
3. Through the gnis-deployment repository


## Acknowledgments

Work on this package was supported by:

[![dataone_footer](https://user-images.githubusercontent.com/6643222/162324180-b5cf0f5f-ae7a-4ca6-87c3-9733a2590634.png)](http://dataone.org)

NSF OIA grant [2033521](https://www.nsf.gov/awardsearch/showAward?AWD_ID=2033521)