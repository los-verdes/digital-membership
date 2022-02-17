tf_subdir      := "./terraform"
db_tf_subdir   := "./terraform/database"
tfvars_file    := "lv-digital-membership.tfvars"

gcr_repo := "gcr.io/lv-digital-membership"
image_tag := `git describe --tags --dirty --long --always`
website_image_name := "website"
website_gcr_image_name := gcr_repo + "/" + website_image_name
worker_image_name := "worker"
worker_gcr_image_name := gcr_repo + "/" + worker_image_name

python_reqs_file := "requirements.txt"
export GCLOUD_PROJECT := "lv-digital-membership"
# TODO: dev as default after we get done setting this all up....
export FLASK_APP := env_var_or_default("FLASK_APP", "wsgi:create_app()")
export FLASK_ENV := env_var_or_default("FLASK_ENV", "developement")
export FLASK_DEBUG := "true"
export LOG_LEVEL := env_var_or_default("LOG_LEVEL", "debug")
export DOCKER_BUILDKIT := "1"
export DIGITAL_MEMBERSHIP_DB_CONNECTION_NAME := "lv-digital-membership:us-central1:lv-digital-membership-6b6a7153"
export DIGITAL_MEMBERSHIP_DB_USERNAME := env_var_or_default("DIGITAL_MEMBERSHIP_DB_USERNAME", `gcloud auth list 2>/dev/null | grep -E '^\*' | awk '{print $2;}'`)
export DIGITAL_MEMBERSHIP_DB_DATABASE_NAME := "lv-digital-membership"
export DIGITAL_MEMBERSHIP_BASE_URL := "localcard.losverd.es:5000"
export GCS_BUCKET_ID := "cstatic.losverd.es"

set-tf-ver-output:
  echo "::set-output name=terraform_version::$(cat {{ tf_subdir }}/.terraform-version)"

tf-db +CMD:
  terraform -chdir="{{ justfile_directory() + "/" + db_tf_subdir }}" \
    {{ CMD }}

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


docker-flask +CMD: build
  @echo "FLASK_APP: ${FLASK_APP-None}"
  @echo "FLASK_ENV: ${FLASK_ENV-None}"
  docker run \
    --interactive \
    --tty \
    --rm \
    --env=APPLE_DEVELOPER_CERTIFICATE \
    --env=APPLE_DEVELOPER_PRIVATE_KEY \
    --env=APPLE_PASS_PRIVATE_KEY_PASSWORD \
    --env=GCS_BUCKET_ID \
    --env=GCLOUD_PROJECT \
    --env=DIGITAL_MEMBERSHIP_DB_CONNECTION_NAME \
    --env=DIGITAL_MEMBERSHIP_DB_USERNAME \
    --env=DIGITAL_MEMBERSHIP_DB_DATABASE_NAME \
    --env=DIGITAL_MEMBERSHIP_DB_ACCESS_TOKEN \
    --env=DIGITAL_MEMBERSHIP_GCP_SECRET_NAME \
    --env=FLASK_APP \
    --env=FLASK_ENV \
    --env=LOG_LEVEL \
    --env=SENDGRID_API_KEY \
    --env=SQUARESPACE_API_KEY \
    --entrypoint='' \
    -v=$HOME/.config/gcloud:/root/.config/gcloud \
    '{{ website_image_name }}' \
    flask {{ CMD }}


flask +CMD:
  @echo "FLASK_APP: ${FLASK_APP-None}"
  @echo "FLASK_ENV: ${FLASK_ENV-None}"
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
  # => export SENDGRID_API_KEY="$(op get item --vault="Los Verdes" 'SendGrid - API Key' | jq -r '.details.sections | .[] | select(.title == "credentials").fields | .[] | select(.n == "credential").v')"
  # => export RECAPTCHA_SECRET_KEY="$(op get item --vault="Los Verdes" 'card.losverd.es - reCAPTCHA' | jq -r '.details.sections | .[] | select(.title == "credentials").fields | .[] | select(.n == "credential").v')"
  # export DIGITAL_MEMBERSHIP_GCP_SECRET_NAME="projects/567739286055/secrets/digital-membership/versions/latest"
  # ~/bin/cloud_sql_proxy -instances='lv-digital-membership:us-central1:lv-digital-membership=tcp:5432'  -enable_iam_login
  # export DIGITAL_MEMBERSHIP_DB_USERNAME="$(gcloud auth list 2>/dev/null | egrep '^\*' | awk '{print $2;}')"
  just flask run --cert=tmp-certs/cert.pem --key=tmp-certs/key.pem --host=0.0.0.0

build-website:
  docker build . --target website --tag '{{ website_image_name }}:{{ image_tag }}'

build-worker:
  docker build . --target worker --tag '{{ worker_image_name }}:{{ image_tag }}'

build: build-website build-worker

build-website-image: ci-install-python-reqs
  just flask build-image website

build-worker-image: ci-install-python-reqs
  just flask build-image worker

build-base-image: ci-install-python-reqs
  just flask build-image base

run-worker: build-worker
  docker run -it --rm '{{ worker_image_name }}:{{ image_tag }}'
shell-worker: build-worker
  docker run -it --rm --entrypoint='' '{{ worker_image_name }}:{{ image_tag }}'  bash

shell-website: build-website
  docker run -it --rm --entrypoint='' '{{ website_image_name }}:{{ image_tag }}'  bash

shell: shell-website

upload-statics: ci-install-python-reqs
  just flask upload-statics

push: build
  echo "Pushing website image..."
  docker tag '{{ website_image_name }}:{{ image_tag }}' '{{ website_gcr_image_name }}:{{ image_tag }}'
  docker tag '{{ website_image_name }}:{{ image_tag }}' '{{ website_gcr_image_name }}:latest'
  docker push '{{ website_gcr_image_name }}:{{ image_tag }}'
  docker push '{{ website_gcr_image_name }}:latest'

  echo "Pushing worker image..."
  docker tag '{{ worker_image_name }}:{{ image_tag }}' '{{ worker_gcr_image_name }}:{{ image_tag }}'
  docker tag '{{ worker_image_name }}:{{ image_tag }}' '{{ worker_gcr_image_name }}:latest'
  docker push '{{ worker_gcr_image_name }}:{{ image_tag }}'
  docker push '{{ worker_gcr_image_name }}:latest'

  echo "Uploading statics..."
  just flask upload-statics

set-tf-output-output output_name:
  output_value="$(just tf output -raw {{ output_name }})"
  echo "::set-output name=output::$output_value"

deploy: ci-install-python-reqs build push
  just tf init
  just tf apply \
    -auto-approve \
    -var='website_image={{ website_gcr_image_name }}:{{ image_tag }}' \
    -var='worker_image={{ worker_gcr_image_name }}:{{ image_tag }}'

configure-database:
  #!/bin/bash
  just tf-db init
  just tf-db apply \
    -auto-approve
  SQL_USER_NAME="$(just tf-db output -raw management_sql_user_name)"
  echo "$SQL_USER_NAME"
  SQL_USER_PASSWORD="$(just tf-db output -raw management_sql_user_password)"
  echo "::add-mask::$SQL_USER_PASSWORD"
  echo "::set-output name=management_sql_user_password::$SQL_USER_PASSWORD"
  echo "::set-output name=management_sql_user_name::$SQL_USER_NAME"

apply-migrations: ci-install-python-reqs
  #!/bin/bash
  echo "DIGITAL_MEMBERSHIP_DB_USERNAME: $DIGITAL_MEMBERSHIP_DB_USERNAME"
  echo "DIGITAL_MEMBERSHIP_DB_ACCESS_TOKEN: $(head -c 5 <<<"$DIGITAL_MEMBERSHIP_DB_ACCESS_TOKEN")"
  just flask db upgrade
  echo 'Any outstanding migrations have now been applied! :D'


sync-subscriptions: ci-install-python-reqs
  @echo "DIGITAL_MEMBERSHIP_DB_DATABASE_NAME: $DIGITAL_MEMBERSHIP_DB_DATABASE_NAME"
  @echo "DIGITAL_MEMBERSHIP_DB_USERNAME: $DIGITAL_MEMBERSHIP_DB_USERNAME"
  @echo "DIGITAL_MEMBERSHIP_DB_CONNECTION_NAME: $DIGITAL_MEMBERSHIP_DB_CONNECTION_NAME"
  @echo "gcloud auth user: $(gcloud auth list 2>/dev/null | grep -E '^\*' | awk '{print $2;}')"
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
  ~/.local/bin/cloud_sql_proxy \
    -instances="$DIGITAL_MEMBERSHIP_DB_CONNECTION_NAME=tcp:5432" \
    ;
  # -enable_iam_login \
  # -token="$(gcloud auth print-access-token --impersonate-service-account=website@lv-digital-membership.iam.gserviceaccount.com)"

remote-psql:
  #!/bin/bash
  PGHOST='127.0.0.1'
  PGPORT='5432'
  gcloud_user=`gcloud auth list 2>/dev/null | grep -E '^\*' | awk '{print $2;}'`
  gcloud_access_token="$(gcloud auth print-access-token)"
  PGUSER="${PGUSER-"$gcloud_user"}"
  PGPASSWORD="${PGPASSWORD-"$gcloud_access_token"}"
  PGDATABASE='lv-digital-membership'
  export PGHOST
  export PGPORT
  export PGUSER
  export PGPASSWORD
  export PGDATABASE
  psql

remote-pg-dump:
  #!/bin/bash
  PGHOST='127.0.0.1'
  PGPORT='5432'
  gcloud_user=`gcloud auth list 2>/dev/null | grep -E '^\*' | awk '{print $2;}'`
  gcloud_access_token="$(gcloud auth print-access-token)"
  PGUSER="${PGUSER-"$gcloud_user"}"
  PGPASSWORD="${PGPASSWORD-"$gcloud_access_token"}"
  PGDATABASE='lv-digital-membership'
  export PGHOST
  export PGPORT
  export PGUSER
  export PGPASSWORD
  export PGDATABASE
  pg_dump --data-only --column-inserts lv-digital-membership > data.sql

gunicorn:
  gunicorn \
    --bind=0.0.0.0:8080 \
    --log-file=- \
    --log-level=info \
    --log-config=config/gunicron_logging.ini \
    'wsgi:create_app()'
