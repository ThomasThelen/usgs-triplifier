FROM ontotext/graphdb:10.8.12
LABEL maintainer="DataONE <support@dataone.org>"

# curl is for the readiness probe in the entrypoint
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# Use uv to manage the python version
COPY --from=ghcr.io/astral-sh/uv:0.10 /uv /uvx /bin/
ENV UV_PYTHON_INSTALL_DIR=/opt/uv/python \
    UV_PROJECT_ENVIRONMENT=/opt/venv

WORKDIR /app

# Copy and install the usgs-triplifier package
COPY usgs-triplifier/ ./usgs-triplifier/
RUN cd usgs-triplifier && uv sync --frozen --no-dev --no-editable
ENV PATH="/opt/venv/bin:$PATH"

# Copy ETL code and config
COPY etl/code/ ./code/
COPY etl/gnis-ld-config.ttl gnis-ld-config.ttl
COPY docker/entrypoint.sh entrypoint.sh
