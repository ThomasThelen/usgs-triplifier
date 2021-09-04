#!/bin/bash
cd "${BASH_SOURCE%/*}" || exit

# triplify nhd
pushd ../
  node ./lib/graphdb/upload.js
  sleep 1h
  node ./lib/graphdb/set-permissions.js
popd
