# Triplifier Base Image

This is the base image used for the triplifier. It handles building and installing the core libraries that the triplifier uses. These dependencies are large and can take a while to build. Since the dependencies rarely change, they're built into this base image which is then used by the triplifier's main Dockerfile.
