const querystring = require('querystring');
const https = require('https');
const fs = require('fs');
const axios = require('axios');
var path = require('path');
const homedir = require('os').homedir();

const tripleFolder = 'lib/data/output/gnis';
// Start by getting a list of all of the turtle files
let filePaths = [];
let symLinkPaths = [];
fs.readdirSync(tripleFolder).forEach(file => {
	let extension = path.extname(file);
	if ('.ttl' === extension) {
		filePaths.push(path.resolve(tripleFolder, file));
	}
});

if (filePaths.length > 0) {
	// Create symlinks in the GraphDB 'Server Files Folder'
	filePaths.forEach((file) => {
		console.log(file);
		const source = homedir+'/graphdb-import/' + path.basename(file);
		symLinkPaths.push(path.basename(file));
		fs.symlink(
			file,
			source,
			(err) => {
				console.error('Problem creating the symlink!', err);
			});
	});


	axios
		.post('http://localhost:7200/rest/data/import/server/gnis-test2', {
			fileNames: symLinkPaths,
		})
		.then(res => {
			console.log(`statusCode: ${res.statusCode}`);
			console.log(res);
		})
		.catch(error => {
			console.error('There was an error uploading the triples to GraphDB: ', error);
		});
}
