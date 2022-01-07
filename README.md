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

The takeaway for contributing is that feature branches are created off of the `develop` branch and pull requests should be made into the `develop` branch rather than `main`.

For example, the workflow to create a pull request for a feature that adds support for fetch.txt follows

- Create an issue describing your planned changes, or add a comment to an existing relevant issue
- Checkout the `develop` branch, followed by `git checkout -b feature_support_fetch_file`
- Commit your changes to the `feature_support_fetch_file` branch
- Create a pull request from `feature_support_fetch_file` into `develop` and outline the code changes and how to test it
- Once the code is reviewed, our team will merge in your changes and you're done!


## Acknowledgments

Work on this package was supported by:

[![dataone_footer](https://www.dataone.org/sites/all/images/DataONE_LOGO.jpg)](http://dataone.org)