curl -X POST --header 'Content-Type: application/json' --header 'Accept: application/json' -d '{
  "fileNames": ["/Users/thomas/usgs-triplifier/feature-aliases.ttl"]
}' localhost:7200/rest/data/import/server/gnis-test2
