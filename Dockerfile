# Dockerfile for USGS Triplifier
FROM gnislinkeddata/triplifier-base
LABEL MAINTAINER "DataONE <support@dataone.org>"

# source code
WORKDIR /src/app
COPY . .

# install software
RUN npm i

# entrypoint
ENTRYPOINT ["npm", "run"]
CMD ["update"]
