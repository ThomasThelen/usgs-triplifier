const axios = require('axios');
var FormData = require('form-data');
const fs = require('fs');
const concat = require("concat-stream")

var graphdb = "http://graphdb";
var bodyFormData = new FormData();
bodyFormData.append("config", fs.createReadStream('./tools/gnis-ld-config.ttl'))
bodyFormData.pipe(concat(data => {
  axios.post(graphdb+":7200/rest/repositories", data, {
    headers: bodyFormData.getHeaders()
  });
}));