# ---- Build stage --------------------------------------------------
FROM python:3.9-slim AS builder

# Make sure the image can reach the Debian mirrors
RUN apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Install build dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential && \
    rm -rf /var/lib/apt/lists/*

# Create and activate virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy & install requirements
COPY requirements.txt .
RUN pip install --no-cache-dir wheel && \
    pip install --no-cache-dir -r requirements.txt

# ---- Final stage --------------------------------------------------
FROM python:3.9-slim

ARG PUID=1000
ARG PGID=1000
ARG UMASK=022

# Copy virtual environment from the builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Make sure we can reach the Debian mirrors again
RUN apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Install runtime libs that Pillow needs
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libfreetype6 \
        libharfbuzz0b \
        libfribidi0 \
        libpng16-16 \
        libjpeg-turbo8 \
        shadow && \
    rm -rf /var/lib/apt/lists/*

# Grab the official gosu binary (works on all arches)
RUN wget -O /usr/local/bin/gosu \
        https://github.com/tianon/gosu/releases/download/1.17-3/gosu-$(dpkg --print-architecture) && \
    chmod +x /usr/local/bin/gosu

# ---- Application --------------------------------------------------
WORKDIR /litkeeper

COPY app app/
COPY run.py .

# Create the data directories (permissions will be fixed by the entrypoint)
RUN mkdir -p app/data/epubs app/data/logs && \
    chmod -R 775 app/data

# Export runtime variables (can be overridden with -e at run‑time)
ENV PUID=${PUID} \
    PGID=${PGID} \
    UMASK=${UMASK} \
    FLASK_APP=app \
    FLASK_ENV=production \
    PYTHONPATH=/litkeeper \
    PYTHONUNBUFFERED=1

# ---- Entrypoint --------------------------------------------------
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]

EXPOSE 5000
CMD ["flask", "run", "--host=0.0.0.0"]
