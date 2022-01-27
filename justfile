tf_subdir      := "./terraform"
tfvars_file    := "lv-digital-membership.tfvars"
gcr_name := "gcr.io/lv-digital-membership/member-card"
gcr_tag := `git describe --tags --dirty --long --always`
gcr_image := gcr_name + ":" + gcr_tag

export GCLOUD_PROJECT := "lv-digital-membership"

set-tf-ver-output:
  echo "::set-output name=terraform_version::$(cat {{ tf_subdir }}/.terraform-version)"

run-tf CMD:
  terraform -chdir="{{ justfile_directory() + "/" + tf_subdir }}" \
    {{ CMD }} \
    {{ if CMD != "init" { "-var-file=../" + tfvars_file } else { "" } }}

tf-init:
  just run-tf init

tf-auto-apply:
  just run-tf 'apply -auto-approve'

flask +CMD:
  flask {{ CMD }}

serve:
  # export DB_SOCKET_DIR={{ justfile_directory() + "./cloudsql"}}
  # ./run_app.py
  # sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain tmp-certs/cert.pem
  flask run --cert=tmp-certs/cert.pem --key=tmp-certs/key.pem

build:
  docker build . --tag 'member-card:latest'

push TAG=`git describe --tags --dirty --long --always`: build
  docker tag 'member-card:latest' '{{ gcr_image }}:{{ TAG }}'
  docker push '{{ gcr_image }}:{{ TAG }}'

deploy:
  echo "{{ gcr_image }}"

  # just run-tf 'apply -auto-approve' -var='cloud_run_container_image={{ gcr_image }}'
