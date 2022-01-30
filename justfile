tf_subdir      := "./terraform"
tfvars_file    := "lv-digital-membership.tfvars"
local_image_name := 'member-card:latest'
gcr_name := "gcr.io/lv-digital-membership/member-card"
gcr_tag := `git describe --tags --dirty --long --always`
gcr_image_name := gcr_name + ":" + gcr_tag
gcr_latest_image_name := gcr_name + ":latest"
python_reqs_file := "requirements.txt"
export GCLOUD_PROJECT := "lv-digital-membership"
# TODO: dev as default after we get done setting this all up....
export FLASK_ENV := env_var_or_default("FLASK_ENV", "developement")
export FLASK_DEBUG := "true"
export LOG_LEVEL := env_var_or_default("LOG_LEVEL", "debug")
export DIGITAL_MEMBERSHIP_DB_CONNECTION_NAME := "lv-digital-membership:us-central1:lv-digital-membership-30c67c90"
export DIGITAL_MEMBERSHIP_DB_USERNAME := env_var_or_default("DIGITAL_MEMBERSHIP_DB_USERNAME", `gcloud auth list 2>/dev/null | grep -E '^\*' | awk '{print $2;}'`)
export DIGITAL_MEMBERSHIP_DB_DATABASE_NAME := "lv-digital-membership"

set-tf-ver-output:
  echo "::set-output name=terraform_version::$(cat {{ tf_subdir }}/.terraform-version)"

tf +CMD:
  terraform -chdir="{{ justfile_directory() + "/" + tf_subdir }}" \
    {{ CMD }} \
    {{ if CMD =~ "(plan|apply)" { "-var-file=../" + tfvars_file } else { "" }  }}

tf-init:
  just tf init

tf-auto-apply:
  just tf 'apply -auto-approve'

ci-install-python-reqs:
  #!/bin/bash
  if [[ '{{ env_var_or_default("CI", "false") }}' == "true" ]]
  then
    echo 'Installing python requirements from {{ python_reqs_file }}...'
    pip3 install \
      --quiet \
      --requirement='{{ python_reqs_file }}'
  else
    echo "skipping pip install outside of GitHub Actions..."
  fi


flask +CMD:
  flask {{ CMD }}

ensure-db-schemas:
  just flask ensure-db-schemas

serve-wsgi:
  ./wsgi.py

serve:
  # export DB_SOCKET_DIR={{ justfile_directory() + "./cloudsql"}}
  # ./run_app.py
  # sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain tmp-certs/cert.pem
  # eval "$(op signin my)"
  # => export APPLE_DEVELOPER_PRIVATE_KEY="$(awk '{printf "%s\\n", $0}' <<<"$(op get document --vault="Los Verdes" 'private.key - Apple Developer Certificate - v0prod - pass.es.losverd.card')")"
  # => export GOOGLE_CLIENT_ID="$(op get item --vault="Los Verdes" 'Local Dev  (Google OAuth Credentials) - Los Verdes Digital Membership' | jq -r '.details.sections | .[] | select(.title == "credentials").fields | .[] | select(.n == "username").v')"
  # => export GOOGLE_CLIENT_SECRET="$(op get item --vault="Los Verdes" 'Local Dev  (Google OAuth Credentials) - Los Verdes Digital Membership' | jq -r '.details.sections | .[] | select(.title == "credentials").fields | .[] | select(.n == "credential").v')"
  # => export APPLE_PASS_PRIVATE_KEY_PASSWORD="$(op get item --vault="Los Verdes" 'private.key password - Apple Developer Certificate - v0prod - pass.es.losverd.card' | jq -r '.details.password')"
  # ~/bin/cloud_sql_proxy -instances='lv-digital-membership:us-central1:lv-digital-membership=tcp:5432'  -enable_iam_login
  # export DIGITAL_MEMBERSHIP_DB_USERNAME="$(gcloud auth list 2>/dev/null | egrep '^\*' | awk '{print $2;}')"
  flask run --cert=tmp-certs/cert.pem --key=tmp-certs/key.pem

build:
  docker build . --tag '{{ local_image_name }}'

shell: build
  docker run -it --rm --entrypoint='' '{{ local_image_name }}' bash

push: build
  docker tag '{{ local_image_name }}' '{{ gcr_image_name }}'
  docker tag '{{ local_image_name }}' '{{ gcr_latest_image_name }}'
  docker push '{{ gcr_image_name }}'
  docker push '{{ gcr_latest_image_name }}'

deploy: build push
  echo "{{ gcr_image_name }}"
  # sed -i'' 's~cloud_run_container_image = .*~cloud_run_container_image = "{{ gcr_image_name }}"~g' lv-digital-membership.tfvars
  just tf init
  just tf apply -auto-approve -var='cloud_run_container_image={{ gcr_image_name }}'

sync-subscriptions: ci-install-python-reqs
  echo $FLASK_ENV
  echo "DIGITAL_MEMBERSHIP_DB_DATABASE_NAME: $DIGITAL_MEMBERSHIP_DB_DATABASE_NAME"
  echo "DIGITAL_MEMBERSHIP_DB_USERNAME: $DIGITAL_MEMBERSHIP_DB_USERNAME"
  echo "DIGITAL_MEMBERSHIP_DB_CONNECTION_NAME: $DIGITAL_MEMBERSHIP_DB_CONNECTION_NAME"
  gcloud auth list 2>/dev/null | grep -E '^\*' | awk '{print $2;}'
  just flask sync-subscriptions

lint:
  # act \
  #   --platform='ubuntu-latest=nektos/act-environments-ubuntu:18.04-full' \
  #   --job=lint
  # VALIDATE_JSCPD_ALL_CODEBASE
  # -e PYTHONPATH
  docker run \
    -e VALIDATE_GITLEAKS=false \
    -e VALIDATE_PYTHON_MYPY=false \
    -e IGNORE_GITIGNORED_FILES=true \
    -e VALIDATE_CSS=false \
    -e VALIDATE_PYTHON_ISORT=false \
    -e VALIDATE_JAVASCRIPT_STANDARD=false \
    -e RUN_LOCAL=true \
    -v '{{ justfile_directory() }}:/tmp/lint' \
    -v '{{ justfile_directory() }}:/tmp/lint/.venv/lib/python3.' \
    github/super-linter

sql-proxy:
  ~/bin/cloud_sql_proxy \
    -instances="$DIGITAL_MEMBERSHIP_DB_CONNECTION_NAME=tcp:5432" \
    -enable_iam_login \
    ;
  # -token="$(gcloud auth print-access-token --impersonate-service-account=website@lv-digital-membership.iam.gserviceaccount.com)"

remote-psql:
  #!/bin/bash
  PGHOST='127.0.0.1'
  PGPORT='5432'
  gcloud_user="website@lv-digital-membership.iam"
  gcloud_access_token="$(gcloud auth print-access-token --impersonate-service-account="$gcloud_user.gserviceaccount.com")"
  PGUSER="${PGUSER-"$gcloud_user"}"
  PGPASSWORD="${PGPASSWORD-"$gcloud_access_token"}"
  PGDATABASE='lv-digital-membership'
  export PGHOST
  export PGPORT
  export PGUSER
  export PGPASSWORD
  export PGDATABASE
  psql
