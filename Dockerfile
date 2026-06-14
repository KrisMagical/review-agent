FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    MGREVIEW_DB_PATH=/data/magicreview.db

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md LICENSE CHANGELOG.md MANIFEST.in ./
COPY app ./app
COPY mcp_server ./mcp_server
COPY magicreview ./magicreview
COPY docs ./docs
COPY examples ./examples

RUN python -m pip install --upgrade pip \
    && python -m pip install ".[all]"

RUN useradd --create-home --shell /bin/sh magicreview \
    && mkdir -p /data \
    && chown -R magicreview:magicreview /data /app

USER magicreview

VOLUME ["/data"]
EXPOSE 8080 8000

CMD ["mgreview", "--help"]
