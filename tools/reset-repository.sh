#!/bin/bash
# Deletes and re-creates the gnis-ld GraphDB repository
curl -X DELETE $GDBHOST:7200/rest/repositories/gnis-ld -H 'Accept: application/json'
# Give GraphDB 30 seconds to delete the repository before re-creating it
sleep 30
# This file is meant to be run from the project's root direcotry, hence the relative path with ./tools/
sh ./tools/create-repository.sh
