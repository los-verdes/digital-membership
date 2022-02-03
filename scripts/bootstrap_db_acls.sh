#!/bin/bash

set -eou pipefail
# function title_case() {
#     gsed 's/.*/\L&/; s/[a-z]*/\u&/g' <<<"$1"
# }

#
# export SQLALCHEMY_DATABASE_URI="$1"
# export SQLALCHEMY_DATABASE_URI="$1"
PGHOST='127.0.0.1'
PGPORT='5432'
gcloud_user="$(gcloud auth list 2>/dev/null | grep -E '^\*' | awk '{print $2;}')" # | sed 's/@/%40/')"
gcloud_access_token="$(gcloud auth print-access-token)"
# gcloud_user="website@lv-digital-membership.iam"
# gcloud_access_token="$(gcloud auth print-access-token --impersonate-service-account=website@lv-digital-membership.iam.gserviceaccount.com)"
PGUSER="${PGUSER-"$gcloud_user"}"
PGPASSWORD="${PGPASSWORD-"$gcloud_access_token"}"
PGDATABASE='lv-digital-membership'
export PGHOST
export PGPORT
export PGUSER
export PGPASSWORD
export PGDATABASE
# GCLOUD_SQL_USERNAME="$(gcloud auth list 2>/dev/null | egrep '^\*' | awk '{print $2;}' | sed 's/@/%40/')"
# GCLOUD_SQL_USERNAME="Jeff.hogan1@gmail.com"
# PGPASSWORD="$(gcloud auth application-default print-access-token)"
# export SQLALCHEMY_DATABASE_URI="postgresql://$GCLOUD_SQL_USERNAME:$GCLOUD_SQL_PASSWORD@127.0.0.1:5432/lv-digital-membership"
# export DATABASE="lv-digital-membership"

RO_USERS=""
RW_USERS="tf-management db-task-runner@lv-digital-membership.iam website@lv-digital-membership.iam worker@lv-digital-membership.iam jeff.hogan1@gmail.com"

TABLE_NAMES="$(\
  echo "SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname != 'pg_catalog' AND schemaname != 'information_schema'" \
    | psql --quiet \
    | tail -n +3 \
    | perl -pe 'chomp if eof' \
    | sed '$ d' \
    | awk '{print $1;}'
)"
echo "TABLE_NAMES: $TABLE_NAMES"


USER_NAMES="$(\
  echo "SELECT usename FROM pg_catalog.pg_user WHERE usename NOT LIKE 'cloudsql%' AND usename NOT IN ('postgres', 'tf-management');" \
    | psql --quiet \
    | tail -n +3 \
    | perl -pe 'chomp if eof' \
    | sed '$ d' \
    | awk '{print $1;}'
)"
echo "USER_NAMES: $USER_NAMES"

echo "Setting up read_only role"
cat << SQL | psql
CREATE ROLE read_only;
\c "$PGDATABASE";
GRANT CONNECT ON DATABASE "$PGDATABASE" TO read_only;
GRANT USAGE ON SCHEMA public TO read_only;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO read_only;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO read_only;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO read_only;
SQL

echo "Setting up read_write role"
cat << SQL | psql
CREATE ROLE read_write;
\c "$PGDATABASE";
GRANT CONNECT ON DATABASE "$PGDATABASE" TO read_write;
GRANT USAGE, CREATE ON SCHEMA public TO read_write;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO read_write;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO read_write;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO read_write;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE ON SEQUENCES TO read_write;
ALTER DEFAULT PRIVILEGES FOR ROLE read_write IN SCHEMA public GRANT SELECT ON TABLES TO read_only;
SQL

TYPE_NAMES="fulfillment_status_enum"
echo "Ensuring types are owned by read_write role...."
for TYPE_NAME in $TYPE_NAMES; do
  echo "ALTER TYPE "'"'"$TYPE_NAME"'"'" OWNER to "'"'"read_write"'"'";" | psql
done

echo "Ensuring tables are owned by read_write role...."
for TABLE_NAME in $TABLE_NAMES; do
  echo "ALTER TABLE "'"'"$TABLE_NAME"'"'" OWNER to "'"'"read_write"'"'";" | psql
done


for RO_USER in $RO_USERS; do
  echo "GRANT read_only to "'"'"$RO_USER"'"'"" | psql
done

for RW_USER in $RW_USERS; do
  echo "GRANT read_write to "'"'"$RW_USER"'"'"" | psql
done
