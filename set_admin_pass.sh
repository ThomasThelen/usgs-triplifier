curl -X PUT --header 'Content-Type: application/json' --header 'Accept: text/plain' --header 'X-GraphDB-Password: <password>' -d '
    {
        appSettings: {
            DEFAULT_SAMEAS: true
            DEFAULT_INFERENCE: true
            EXECUTE_COUNT: true
            IGNORE_SHARED_QUERIES: false
            },
        grantedAuthorities: ["ROLE_ADMIN"],
        pass: "admin",
        username: "root"
    }' http://localhost:7200/rest/security/user/admin


    # curl http://localhost:7200/rest/security/user
