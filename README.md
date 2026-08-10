# USGS Triplifier

The ETL process and graph database for gnis-ld.org data

- **Authors**: [Blake Regalia](https://github.com/blake-regalia), Thomas Thelen ([NCEAS](http://www.nceas.ucsb.edu))
- **License**: [Apache 2](http://opensource.org/licenses/Apache-2.0)
- [**Submit Bugs and feature requests**](https://github.com/DataONEorg/usgs-triplifier/issues)
- Contact us: support@dataone.org
- [DataONE discussions](https://github.com/DataONEorg/dataone/discussions)

## Background

<<<<<<< Updated upstream
The USGS has structured information about places. This includes things like names, elevations, types, etc. This repository hosts code that ingests this data, transforms it to fit the GNIS and USGS ontologies, and then uploads it to GraphDB.

## Development

`base/`: Contains the base docker image that the triplifier uses.

`lib/`: Contains the javascript responsible for most of the application logic around triplification.

`tools/`: Shell scripts to control the triplifier; called through npm. These are run in series, which execute the javascript in `lib/`.

### Running

The triplifier is meant to be run within the DataONE Kubernetes ecosystem. The kubernetes deployment files and instructions can be found [here](https://github.com/DataONEorg/gnis-deployment).

To test under develop conditions

1. Make code changes
2. Build image, tag it
3. Change the image in the deployment repository to match the one in (3)
4. Follow deployment instructions
=======
The USGS hosts several data products that contain information about places: their location, name(s), descriptions, geometries, etc. These files are hosted in several formats: text, gdb, and gpkg. This repository contains

1. A python library for converting the names database in the gpkg data format to RDF
2. A graph database service for hosting the data
3. An ETL process for fetching the data from USGS, transforming it into RDF, and loading it into the graph database

## Development

The general idea is that any changes to the generation of triples happens in the `usgs_triplifier` package. After each change, increment the version. The deployment system should then have its `usgs_triplifier` version changed to the new one, any refactorings, and re-deployed.

### Docker Image
>>>>>>> Stashed changes

The dockerfile in the `docker` folder is used to create the image for serving GraphDB both locally and with kubernetes. The image is included with an entrypoint script that should be run to configure the repository and perform the data etl.

<<<<<<< Updated upstream
All contributions are welcome! For more information how how to fork, branch, and make pull requests visit the [contributing](./CONTRIBUTING.md) guide.
=======
### Testing

There are two ways to play with things:

1. Directly calling the ugs-triplifier package via `python -m <one of the modules here>`
2. By running the local docker stack and letting automation download, triplify, and upload

```bash
cd docker
docker compose up
```

## Notes

- The logging isn't perfect; once 
- The usgs-triplifier package isn't being used as a package - its folder is being copied in the Dockerfile
- Triplifying and writing takes a while; no parallelization

>>>>>>> Stashed changes

## Acknowledgments

Work on this package was supported by:

[![dataone_footer](https://user-images.githubusercontent.com/6643222/162324180-b5cf0f5f-ae7a-4ca6-87c3-9733a2590634.png)](http://dataone.org)

NSF OIA grant [2033521](https://www.nsf.gov/awardsearch/showAward?AWD_ID=2033521)