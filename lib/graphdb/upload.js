const querystring = require('querystring');
const https = require('https');
const fs = require('fs');
const axios = require('axios');
var path = require('path');
const homedir = require('os').homedir();
const mkdirp = require('mkdirp');
const fse = require('fs-extra');



var uploadDir = '/root/graphdb-import/';
if(!fs.existsSync(uploadDir)){
  mkdirp.sync(uploadDir);
}

const tripleFolder = './data/output/gnis/';
// Start by getting a list of all of the turtle files
let filePaths = [];
let symLinkPaths = [];
fs.readdirSync(tripleFolder).forEach(file => {
	let extension = path.extname(file);
	if ('.ttl' === extension) {
    fullPath = path.resolve(tripleFolder, file);
		filePaths.push(fullPath);
	}
});

if (filePaths.length > 0) {
	// Create symlinks in the GraphDB 'Server Files Folder'
	filePaths.forEach((file) => {
		const dest = '/root/graphdb-import/' + path.basename(file);
		symLinkPaths.push(path.basename(file));

    // File is overwritten by default
    //require('child_process').spawn('cp', ['-r', path.resolve(file), dest]);
    fse.copySync(path.resolve(file), dest, { overwrite: true }, function (err) {
      if (err) {
        console.error(err);
      }
    });

	  });
  
    
  host = `http://localhost`;
	axios
		.post(host+':7200/rest/data/import/server/gnis-ld', {
			fileNames: symLinkPaths,
		})
		.then(res => {
			console.log('Uploaded the triples to GraphDB', res);
		})
		.catch(error => {
			console.error('There was an error uploading the triples to GraphDB: ', error);
		});
} else {
  console.error("Failed to find any triple files that should be sent to GraphDB");
}
