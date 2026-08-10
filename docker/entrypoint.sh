#!/bin/bash

/opt/graphdb/dist/bin/graphdb &
GRAPHDB_PID=$!

echo 'Waiting for GraphDB to be ready...'
until curl -sf http://localhost:7200/rest/repositories > /dev/null 2>&1; do
    sleep 5
done
echo 'GraphDB is ready'

cd /app && python3 code/etl.py

echo 'ETL complete. GraphDB is serving traffic...'
wait $GRAPHDB_PID
