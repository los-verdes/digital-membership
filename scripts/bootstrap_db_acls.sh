#!/bin/bash

set -exou pipefail

export SQLALCHEMY_DATABASE_URI="$1"
export DATABASE="lv-digital-membership"

RO_USERS=""
RW_USERS="tf-management website@lv-digital-membership.iam Jeff.hogan1@gmail.com"

echo "Setting up read_only role"
cat << SQL | psql "$SQLALCHEMY_DATABASE_URI"
CREATE ROLE read_only;
\c "$DATABASE";
GRANT CONNECT ON DATABASE "$DATABASE" TO read_only;
GRANT USAGE ON SCHEMA public TO read_only;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO read_only;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO read_only;
SQL

cat << SQL | psql "$SQLALCHEMY_DATABASE_URI"
CREATE ROLE read_write;
\c "$DATABASE";
GRANT CONNECT ON DATABASE "$DATABASE" TO read_write;
GRANT USAGE, CREATE ON SCHEMA public TO read_write;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO read_write;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO read_write;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO read_write;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE ON SEQUENCES TO read_write;
ALTER DEFAULT PRIVILEGES FOR ROLE read_write IN SCHEMA public GRANT SELECT ON TABLES TO read_only;
SQL

for RO_USER in $RO_USERS; do
  echo "GRANT read_only to "'"'"$RO_USER"'"'"" | psql "$SQLALCHEMY_DATABASE_URI"
done

for RW_USER in $RW_USERS; do
  echo "GRANT read_write to "'"'"$RW_USER"'"'"" | psql "$SQLALCHEMY_DATABASE_URI"
done
