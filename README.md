# USGS Triplifier

A dockerized application for turning the USGS GNIS dataset into linked data triples.

- **Authors**: [Blake Regalia](https://github.com/blake-regalia), Thomas Thelen ([NCEAS](http://www.nceas.ucsb.edu))
- **License**: [Apache 2](http://opensource.org/licenses/Apache-2.0)
- [**Submit Bugs and feature requests**](https://github.com/DataONEorg/usgs-triplifier/issues)
- Contact us: support@dataone.org
- [DataONE discussions](https://github.com/DataONEorg/dataone/discussions)

## Background

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

### Contributing

All contributions are welcome! For more information how how to fork, branch, and make pull requests visit the [contributing](./CONTRIBUTING.md) guide.

## Acknowledgments

Work on this package was supported by:

[![dataone_footer](https://user-images.githubusercontent.com/6643222/162324180-b5cf0f5f-ae7a-4ca6-87c3-9733a2590634.png)](http://dataone.org)

NSF OIA grant [2033521](https://www.nsf.gov/awardsearch/showAward?AWD_ID=2033521)