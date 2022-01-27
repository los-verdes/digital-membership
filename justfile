tf_subdir      := "./terraform"
tfvars_file    := "lv-digital-membership.tfvars"
local_image_name := 'member-card:latest'
gcr_name := "gcr.io/lv-digital-membership/member-card"
gcr_tag := `git describe --tags --dirty --long --always`
gcr_image_name := gcr_name + ":" + gcr_tag

export GCLOUD_PROJECT := "lv-digital-membership"
export GOOGLE_CLOUD_PROJECT := "lv-digital-membership"

set-tf-ver-output:
  echo "::set-output name=terraform_version::$(cat {{ tf_subdir }}/.terraform-version)"

run-tf +CMD:
  terraform -chdir="{{ justfile_directory() + "/" + tf_subdir }}" \
    {{ CMD }} \
    {{ if CMD =~ "init" { "" } else { "-var-file=../" + tfvars_file } }}

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
  docker build . --tag '{{ local_image_name }}'

push: build
  docker tag '{{ local_image_name }}' '{{ gcr_image_name }}'
  docker push '{{ gcr_image_name }}'

deploy: build push
  echo "{{ gcr_image_name }}"

  just run-tf apply -auto-approve -var='cloud_run_container_image={{ gcr_image_name }}'
