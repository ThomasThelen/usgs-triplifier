#!/bin/bash

cd "${BASH_SOURCE%/*}" || exit

# triplify nhd
pushd ../
	node ./lib/graphdb/upload.js
popd
