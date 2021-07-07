#!/bin/bash
curl -X POST localhsot:7200/rest/repositories?location=<encoded_location_uri> -H 'Accept: application/json' -H 'Content-Type: multipart/form-data' -F config=@gnis-ld-config.ttl
