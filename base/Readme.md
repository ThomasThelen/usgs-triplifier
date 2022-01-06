This is the base image used for the triplifier. It handles installing libraries that can take a while to build during development (eg GDAL). Since this layer doesn't need to change often, it's used as a base image for the triplifier.

To build and push run `docker build -t gnislinkeddata/triplifier-base .` and `docker push gnislinkeddata/triplifier-base`.