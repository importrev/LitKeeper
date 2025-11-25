#!/bin/sh
# ------------------------------------------------------------------
#  entrypoint.sh – create user, set ownership & umask, then run Flask
# ------------------------------------------------------------------
set -e

if ! id -u litkeeper >/dev/null 2>&1; then
    if ! getent group litkeeper >/dev/null 2>&1; then
        groupadd -g "$PGID" litkeeper
    fi
    useradd -u "$PUID" -g "$PGID" -s /usr/sbin/nologin -M litkeeper

    chown -R litkeeper:litkeeper app/data
fi

umask "$UMASK"
r
exec gosu litkeeper "$@"
