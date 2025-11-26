# Build stage
FROM python:3.9-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
        --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create and activate virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy and install requirements
COPY requirements.txt .
RUN pip install --no-cache-dir wheel && \
    pip install --no-cache-dir -r requirements.txt

# Final stage
FROM python:3.9-slim


ARG PUID=1000
ARG PGID=1000
ARG UMASK=022

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install runtime libraries that Pillow needs
RUN apt-get update && apt-get install -y --no-install-recommends \
        libfreetype6 \
        libharfbuzz0b \
        libfribidi0 \
        libpng16-16 \
        libjpeg62-turbo \
        shadow && \
    rm -rf /var/lib/apt/lists/*


# Grab the official gosu binary (works on all arches)
RUN wget -O /usr/local/bin/gosu \
        https://github.com/tianon/gosu/releases/download/1.17-3/gosu-$(dpkg --print-architecture) && \
    chmod +x /usr/local/bin/gosu

# ------------------------------------------------------------------
# 3. Application
# ------------------------------------------------------------------
WORKDIR /litkeeper

# Copy only necessary files
COPY app app/
COPY run.py .


# Create data directories with correct permissions
RUN mkdir -p app/data/epubs app/data/logs && \
    chmod -R 775 app/data

# Export the same values to the runtime env (so you can override at build time)
ENV PUID=${PUID} \
    PGID=${PGID} \
    UMASK=${UMASK} \
    FLASK_APP=app \
    FLASK_ENV=production \
    PYTHONPATH=/litkeeper \
    PYTHONUNBUFFERED=1
# Run the application with Flask development server
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]

EXPOSE 5000
CMD ["flask", "run", "--host=0.0.0.0"]
