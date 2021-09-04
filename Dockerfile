# Dockerfile for USGS Triplifier
FROM thomasthelen/triplifier-base:latest

# source code
WORKDIR /src/app
COPY . .

# install software
RUN npm i

# entrypoint
ENTRYPOINT ["npm", "run"]
CMD ["update"]
