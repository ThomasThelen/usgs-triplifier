FROM node:lts-bullseye
LABEL MAINTAINER "DataONE <support@dataone.org>"

# add PostgreSQL keys
RUN wget -q https://www.postgresql.org/media/keys/ACCC4CF8.asc -O - | apt-key add -
RUN echo "deb http://apt.postgresql.org/pub/repos/apt/ stretch-pgdg main" > /etc/apt/sources.list.d/pgdg.list

# install packages
RUN apt-get -y update \
    && apt-get upgrade -y \
    && apt-get install -yq \
        curl \
        git \
        vim \
        libpq-dev \
        postgresql-client-common \
        postgresql-client \
        sqlite3 \
        libsqlite3-dev \
    && apt-get clean

# downloda Proj
ENV PROJ_VERSION 8.0.1
RUN mkdir -p /src/proj
ADD https://github.com/OSGeo/PROJ/releases/download/${PROJ_VERSION}/proj-${PROJ_VERSION}.tar.gz /src/proj

# install proj
RUN cd /src/proj \
    && tar -xvf proj-${PROJ_VERSION}.tar.gz \
    && cd proj-${PROJ_VERSION} \
    && ./configure \
    && make install

# download GDAL 3
ENV GDAL_VERSION 3.3.0
RUN mkdir -p /src/gdal3
ADD http://download.osgeo.org/gdal/${GDAL_VERSION}/gdal-${GDAL_VERSION}.tar.gz /src/gdal3

# install GDAL 3
RUN cd /src/gdal3 \
    && tar -xvf gdal-${GDAL_VERSION}.tar.gz \
    && cd gdal-${GDAL_VERSION} \
    && ./configure --with-pg --with-curl --with-proj=/usr/local \
    && make \
    && make install \
    && ldconfig \
    && rm -Rf /src/gdal3/*
