tf_subdir      := "./terraform"
db_tf_subdir   := "./terraform/database"
bootstrap_tf_subdir   := "./terraform/bootstrap"
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
export FLASK_ENV := env_var_or_default("FLASK_ENV", "development")
export FLASK_DEBUG := "true"
export LOG_LEVEL := env_var_or_default("LOG_LEVEL", "debug")
export DOCKER_BUILDKIT := "1"
export DIGITAL_MEMBERSHIP_GCP_SQL_CONNECTION_NAME := "lv-digital-membership:us-central1:lv-digital-membership-6b6a7153"
export DIGITAL_MEMBERSHIP_DB_USERNAME := env_var_or_default("DIGITAL_MEMBERSHIP_DB_USERNAME", `gcloud auth list 2>/dev/null | grep -E '^\*' | awk '{print $2;}'`)
# export DIGITAL_MEMBERSHIP_DB_USERNAME := "website@lv-digital-membership.iam"
export DIGITAL_MEMBERSHIP_DB_DATABASE_NAME := "lv-digital-membership"
# export DIGITAL_MEMBERSHIP_BASE_URL := "tunnelcard.losverd.es"
# export SERVER_NAME := "tunnelcard.losverd.es"
export GCS_BUCKET_ID := "cstatic.losverd.es"



onepass_session:
  echo op whoami || eval "$(op signin --account my.1password.com)"

# TODO: This is all from the beforetimes and should be tidied up!

set-tf-ver-output:
  echo "terraform_version=$(cat {{ tf_subdir }}/.terraform-version)" | tee --append "$GITHUB_OUTPUT"

tf-bootstrap +CMD:
  terraform -chdir="{{ justfile_directory() + "/" + bootstrap_tf_subdir }}" \
    {{ CMD }} \
    {{ if CMD =~ "(plan|apply)" { "-var-file=../../" + tfvars_file } else { "" }  }}


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

ci-install-test-python-reqs:
  #!/bin/bash

  set -eou pipefail

  if [[ '{{ env_var_or_default("CI", "false") }}' == "true" ]]
  then
    pip3 install \
      --quiet \
      --requirement='requirements-test.in'
  else
    echo "skipping pip install outside of GitHub Actions..."
  fi

ci-install-python-reqs:
  #!/bin/bash

  set -eou pipefail

  if [[ '{{ env_var_or_default("CI", "false") }}' == "true" ]]
  then
    echo 'Installing python requirements from {{ python_reqs_file }}...'
    pip3 install \
      --quiet \
      --requirement='{{ python_reqs_file }}'
  else
    echo "skipping pip install outside of GitHub Actions..."
  fi


docker-flask +CMD: build onepass_session
  @echo "FLASK_APP: ${FLASK_APP-None}"
  @echo "FLASK_ENV: ${FLASK_ENV-None}"
  op run --env-file='./.env' -- \
    docker run \
    --interactive \
    --tty \
    --rm \
    --env=DIGITAL_MEMBERSHIP_SECRETS_JSON \
    --env=FLASK_APP \
    --env=FLASK_ENV \
    --env=LOG_LEVEL \
    --entrypoint='' \
    -v=$HOME/.config/gcloud:/root/.config/gcloud \
    '{{ website_image_name }}' \
    flask {{ CMD }}


flask +CMD:
  #!/bin/bash
  echo "FLASK_APP: ${FLASK_APP-None}"
  echo "FLASK_ENV: ${FLASK_ENV-None}"
  flask {{ CMD }}


secret-flask +CMD:
  #!/bin/bash
  echo "FLASK_APP: ${FLASK_APP-None}"
  echo "FLASK_ENV: ${FLASK_ENV-None}"
  export OP_ACCOUNT="my.1password.com"
  export DIGITAL_MEMBERSHIP_SECRETS_JSON="op://Los Verdes/digital-membership_local_dev_secrets/value"
  # export DIGITAL_MEMBERSHIP_SECRETS_JSON="op://Los Verdes/digital-membership_gcp-secrets-manager/value"
  op run -- flask {{ CMD }}

ensure-db-schemas:
  just flask ensure-db-schemas

serve-wsgi:
  ./wsgi.py

# export DIGITAL_MEMBERSHIP_GCP_SECRET_NAME="projects/567739286055/secrets/digital-membership/versions/latest"
# ~/bin/cloud_sql_proxy -instances='lv-digital-membership:us-central1:lv-digital-membership=tcp:5432'  -enable_iam_login
# export DIGITAL_MEMBERSHIP_DB_USERNAME="$(gcloud auth list 2>/dev/null | egrep '^\*' | awk '{print $2;}')"

serve: onepass_session
  #!/bin/zsh
  # source /Users/jeffwecan/.pyenv/versions/3.9.2/bin/virtualenvwrapper.sh
  # workon digital-membership
  just flask run --cert=tmp-certs/flask-cert.pem --key=tmp-certs/flask-key.pem --host=0.0.0.0 --port=8080

build-website:
  docker build . --target website --tag '{{ website_image_name }}:{{ image_tag }}'

build-worker:
  docker build . --target worker --tag '{{ worker_image_name }}:{{ image_tag }}'

build: build-website build-worker

cloudbuild CONFIG_FILE *SUBSTITUTIONS="":
  #!/bin/bash

  logfile=$(mktemp /tmp/local_config_apply.XXXXXXXXXX) || { echo "Failed to create temp file"; exit 1; }

  gcloud builds submit {{ justfile_directory() }} \
    --format='json' \
    --config="{{ CONFIG_FILE }}" \
    --suppress-logs \
    --substitutions='_IMAGE_TAG={{ image_tag }}{{ if SUBSTITUTIONS != "" { "," + SUBSTITUTIONS } else { "" } }}' \
  | tee "$logfile"

  IMAGE_OUTPUT="$(jq -r '.images[0]' "$logfile")"
  echo
  echo "BUILD RESULTS:"
  jq -r '.' "$logfile"
  echo "IMAGE_OUTPUT: ${IMAGE_OUTPUT}"
  echo

  if [[ -n "$IMAGE_OUTPUT" ]]
  then
    echo "image=$IMAGE_OUTPUT" | tee --append "$GITHUB_OUTPUT"
  fi

cloudbuild-image-website:
  just cloudbuild 'cloudbuild.yaml' '_BUILD_TARGET=website'

cloudbuild-image-worker:
  just cloudbuild 'cloudbuild.yaml' '_BUILD_TARGET=worker'

cloudbuild-upload-statics _BUCKET_ID='cstatic.losverd.es':
  just cloudbuild 'cloudbuild-statics.yaml' '_BUCKET_ID={{ _BUCKET_ID }}'

run-worker: build-worker
  docker run -it --rm '{{ worker_image_name }}:{{ image_tag }}'

shell-worker: build-worker
  docker run -it --rm --entrypoint='' '{{ worker_image_name }}:{{ image_tag }}'  bash

shell-website: build-website
  docker run -it --rm --entrypoint='' '{{ website_image_name }}:{{ image_tag }}'  bash

shell: shell-website

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


set-tf-output-output output_name:
  output_value="$(just tf output -raw {{ output_name }})"
  echo "output=$output_value" | tee --append "$GITHUB_OUTPUT"

deploy: ci-install-python-reqs build push
  just tf init
  just tf apply \
    -auto-approve \
    -var='website_image={{ website_gcr_image_name }}:{{ image_tag }}' \
    -var='worker_image={{ worker_gcr_image_name }}:{{ image_tag }}'

configure-database:
  #!/bin/bash

  set -eou pipefail

  just tf-db init
  just tf-db apply \
    -auto-approve
  SQL_USER_NAME="$(just tf-db output -raw management_sql_user_name)"
  echo "$SQL_USER_NAME"
  echo "management_sql_user_name=$SQL_USER_NAME" | tee --append "$GITHUB_OUTPUT"

apply-migrations: ci-install-python-reqs
  #!/bin/bash

  set -eou pipefail

  echo "DIGITAL_MEMBERSHIP_DB_USERNAME: $DIGITAL_MEMBERSHIP_DB_USERNAME"
  echo "DIGITAL_MEMBERSHIP_DB_ACCESS_TOKEN: $(head -c 5 <<<"$DIGITAL_MEMBERSHIP_DB_ACCESS_TOKEN")"
  just flask db upgrade
  echo 'Any outstanding migrations have now been applied! :D'

sync-subscriptions: ci-install-python-reqs
  @echo "DIGITAL_MEMBERSHIP_DB_DATABASE_NAME: $DIGITAL_MEMBERSHIP_DB_DATABASE_NAME"
  @echo "DIGITAL_MEMBERSHIP_DB_USERNAME: $DIGITAL_MEMBERSHIP_DB_USERNAME"
  @echo "DIGITAL_MEMBERSHIP_GCP_SQL_CONNECTION_NAME: $DIGITAL_MEMBERSHIP_GCP_SQL_CONNECTION_NAME"
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
    "$DIGITAL_MEMBERSHIP_GCP_SQL_CONNECTION_NAME" \
    --port=5434 \
    --auto-iam-authn \
    --token="$(gcloud auth print-access-token)"  \
    --login-token="$(gcloud auth print-access-token --impersonate-service-account=website@lv-digital-membership.iam.gserviceaccount.com)";
  # --enable_iam_login \

remote-psql:
  psql \
    --username='website@lv-digital-membership.iam' \
    --host=127.0.0.1 \
    --port=5434 \
    lv-digital-membership

remote-pg-dump:
  pg_dump \
    --username='website@lv-digital-membership.iam' \
    --host=127.0.0.1 \
    --port=5434 \
    --data-only \
    --column-inserts \
    lv-digital-membership \
  > data.sql.bak

gunicorn:
  gunicorn \
    --bind=0.0.0.0:8080 \
    --log-file=- \
    --log-level=info \
    --log-config=config/gunicron_logging.ini \
    'wsgi:create_app()'

ci-bootstrap-test-db:
  #!/bin/bash

  set -eou pipefail

  if [[ '{{ env_var_or_default("CI", "false") }}' == "true" ]]
  then
    ./tests/config/sql/bootstrap.sh
  fi

test *FLAGS:
  python -m pytest \
    --durations=10 \
    --log-level=DEBUG \
    --cov=member_card \
    {{ FLAGS }}

local-test *FLAGS:
  just test \
    --capture="tee-sys" \
    --cov-report=term-missing \
    --verbose \
    {{ FLAGS }}

debug-test *FLAGS:
  just local-test --pdb {{ FLAGS }}

ci-test: ci-install-test-python-reqs ci-bootstrap-test-db
  just local-test \
    --cov-report=xml

widget-builder CMD *ARGS:
  op run --env-file='./widget_workshop/.env_dev' -- \
    widget-builder {{CMD }} \
    {{ ARGS }}

widget-start:
  just widget-builder start \
      widget_workshop/membership_card \
      --auto-open=false

widget-validate:
  just widget-builder validate \
      widget_workshop/membership_card

widget-publish:
  just widget-builder publish \
      membership_info

check-bigcomm-regions:
  #!/bin/zsh

  set -x
  op run --no-masking --env-file=<(echo "export BIGCOMM_ACCESS_TOKEN='op://Los Verdes/bigcommerce_api_creds_dev/access_token'") -- \
    bash -c '\
      curl -v \
        --header "X-Auth-Token:$BIGCOMM_ACCESS_TOKEN" \
        "https://api.bigcommerce.com/stores/hgp7pebwfj/v3/content/regions?template_file=pages/category" \
    '


check-bigcomm-channels:
  #!/bin/zsh

  set -x
  op run --no-masking --env-file=<(echo "export BIGCOMM_ACCESS_TOKEN='op://Los Verdes/bigcommerce_api_creds_dev/access_token'") -- \
    bash -c '\
      curl -v \
        --header "X-Auth-Token:$BIGCOMM_ACCESS_TOKEN" \
        "https://api.bigcommerce.com/stores/hgp7pebwfj/v3/channels" \
    '
