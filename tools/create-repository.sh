#!/bin/bash
curl -X POST $GDBHOST:7200/rest/repositories -H 'Accept: application/json' -H 'Content-Type: multipart/form-data' -F config=@tools/gnis-ld-config.ttl
