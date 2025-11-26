# -------------------------------------------------------------
# 1️⃣  Build stage – copy source, install Python deps only
# -------------------------------------------------------------
FROM python:3.9-slim-buster AS builder

# Create & activate a virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy the dependency list and install them
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# -------------------------------------------------------------
# 2️⃣  Final stage – runtime image
# -------------------------------------------------------------
FROM python:3.9-slim-buster

ARG PUID=1000
ARG PGID=1000
ARG UMASK=022

# Copy the virtual env from the builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Grab the official gosu binary (works on all architectures)
RUN wget -O /usr/local/bin/gosu \
        https://github.com/tianon/gosu/releases/download/1.17-3/gosu-$(dpkg --print-architecture) && \
    chmod +x /usr/local/bin/gosu

# -------------------------------------------------------------
# 3️⃣  Application
# -------------------------------------------------------------
WORKDIR /litkeeper

COPY app app/
COPY run.py .

# Create the data directories – permissions will be fixed by the entrypoint
RUN mkdir -p app/data/epubs app/data/logs && \
    chmod -R 775 app/data

# Export runtime variables (overridable with -e)
ENV PUID=${PUID} \
    PGID=${PGID} \
    UMASK=${UMASK} \
    FLASK_APP=app \
    FLASK_ENV=production \
    PYTHONPATH=/litkeeper \
    PYTHONUNBUFFERED=1

# -------------------------------------------------------------
# 4️⃣  Entrypoint – creates user/group, sets umask, drops to user
# -------------------------------------------------------------
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]

EXPOSE 5000
CMD ["flask", "run", "--host=0.0.0.0"]
