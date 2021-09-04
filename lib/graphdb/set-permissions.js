const axios = require('axios');

    // Set free access to the gnis-ld repository
    axios
    .post('http://localhost:7200/rest/security/freeaccess',{
      "appSettings": {
        "DEFAULT_SAMEAS": true,
        "DEFAULT_INFERENCE": true,
        "EXECUTE_COUNT": true,
        "IGNORE_SHARED_QUERIES": false
      },
      authorities: ["READ_REPO_gnis-ld"],
      enabled: true
},{
      headers: {
        'Accept': 'text/plain'
      }
    }).then(res => {
      console.log("Set the 'gnis-ld' repository to read-only.");
      setPassword();
  
    }).catch(error => {
      console.error("Failed make the 'gnis-ld' repository read only.", error);
    });

setPassword = function(){
// Set a new password for the administrator account
axios
.put('http://localhost:7200/rest/security/user/admin', {
  appSettings: {
    DEFAULT_SAMEAS: true,
    DEFAULT_INFERENCE: true,
    EXECUTE_COUNT: true,
    IGNORE_SHARED_QUERIES: false
  },
  grantedAuthorities: ["ROLE_ADMIN"],
  pass: "pass",
  username: "admin"
},
{
  headers: {
  'Accept': 'text/plain',
  'X-GraphDB-Password': 'root'
  }
})
.then(res => {
  // After the admin account is set, enable security
  axios
  .post('http://localhost:7200/rest/security', "true",{
    headers: {
      'Content-Type': 'application/json',
       'Accept': 'text/plain'
    }
  }).then(res => {
    console.log("Enabled GraphDB security");
  }).catch(error => {
    console.error("Failed to enable GraphDB security.", error);
  });
}).then(res => {
  console.log("Set the GraphDB password.");
})
.catch(error => {
  console.error('Failed to set the GraphDB admin account. ', error);
});
}