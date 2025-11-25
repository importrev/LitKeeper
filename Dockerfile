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

# Install only runtime dependencies
RUN apt-get update && apt-get install -y \
    --no-install-recommends \
    libfreetype6 \
    libharfbuzz0b \
    libfribidi0 \
    libpng16-16 \
    libjpeg62-turbo \
    shadow \   
    gosu \
    && rm -rf /var/lib/apt/lists/*

# Set up application directory
WORKDIR /litkeeper

# Copy only necessary files
COPY app app/
COPY run.py .


# Create data directories with correct permissions
RUN mkdir -p app/data/epubs app/data/logs && \
    chmod -R 775 app/data
RUN groupadd --gid ${PGID} litkeeper && \
    useradd --uid ${PUID} --gid ${PGID} --shell /usr/sbin/nologin -M litkeeper && \
    chown -R litkeeper:litkeeper app/data
    
# Set environment variables
ENV PUID=1000
ENV PGID=1000
ENV UMASK=022
ENV FLASK_APP=app
ENV FLASK_ENV=production
ENV PYTHONPATH=/litkeeper
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 5000

# Run the application with Flask development server
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]

CMD ["flask", "run", "--host=0.0.0.0"]
