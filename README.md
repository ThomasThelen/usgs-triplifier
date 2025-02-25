# USGS Triplifier

A dockerized application for turning the USGS GNIS dataset into linked data triples.

- **Authors**: [Blake Regalia](https://github.com/blake-regalia), Thomas Thelen ([NCEAS](http://www.nceas.ucsb.edu))
- **License**: [Apache 2](http://opensource.org/licenses/Apache-2.0)
- [**Submit Bugs and feature requests**](https://github.com/DataONEorg/usgs-triplifier/issues)

## Background

The usgs triplifier stack ingests the USGS GNIS dataset and transforms a subset of the data into the RDF data model in the turtle format.

## Development

`base/`: Contains the base docker image that the triplifier uses.
`lib/`: Contains the javascript responsible for most of the application logic around triplification.
`tools/`: Shell scripts that are called from npm. These are run in series, which execute the javascript in `lib/`.

### Contributing

All contributions are welcome! For more information how how to fork, branch, and make pull requests visit the [contributing](./CONTRIBUTING.md) guide.

## Acknowledgments

Work on this package was supported by:

[![dataone_footer](https://www.dataone.org/sites/all/images/DataONE_LOGO.jpg)](http://dataone.org)
