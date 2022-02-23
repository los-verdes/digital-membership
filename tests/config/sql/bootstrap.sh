#!/bin/bash

set -eoxu pipefail

POSTGRES_DB="${POSTGRES_DB-lv-digital-membership-tests}"
POSTGRES_USER="${POSTGRES_USER-postgres}"

PGHOST="${PGHOST-127.0.0.1}"
PGPORT="${PGPORT-5433}"

PGUSER="${POSTGRES_USER-postgres}"
PGPASSWORD="${PGPASSWORD-postgres}"

export PGHOST
export PGPORT
export PGUSER
export PGPASSWORD

echo "Setting up 'test-runner' user"
psql -v ON_ERROR_STOP=1 --dbname "$POSTGRES_DB" <<-EOSQL
CREATE USER "test-runner";
ALTER USER "test-runner" with encrypted password 'hi-im-testing';
GRANT ALL PRIVILEGES ON DATABASE "$POSTGRES_DB" TO "test-runner";
EOSQL

echo "Setting up read_only role"
psql -v ON_ERROR_STOP=1 --dbname "$POSTGRES_DB" <<-EOSQL
CREATE ROLE read_only;
GRANT USAGE ON SCHEMA public TO read_only;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO read_only;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO read_only;
GRANT read_only to "test-runner";
EOSQL

echo "Setting up read_write role"
psql -v ON_ERROR_STOP=1 --dbname "$POSTGRES_DB" <<-EOSQL
CREATE ROLE read_write;
GRANT USAGE, CREATE ON SCHEMA public TO read_write;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO read_write;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO read_write;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO read_write;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE ON SEQUENCES TO read_write;
ALTER DEFAULT PRIVILEGES FOR ROLE read_write IN SCHEMA public GRANT SELECT ON TABLES TO read_only;
GRANT read_write to "test-runner";
EOSQL
