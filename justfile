tf_subdir      := "./terraform"
tfvars_file    := "lv-digital-membership.tfvars"
local_image_name := 'member-card:latest'
gcr_name := "gcr.io/lv-digital-membership/member-card"
gcr_tag := `git describe --tags --dirty --long --always`
gcr_image_name := gcr_name + ":" + gcr_tag
gcr_latest_image_name := gcr_name + ":latest"

export GCLOUD_PROJECT := "lv-digital-membership"

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

flask +CMD:
  flask {{ CMD }}

serve:
  # export DB_SOCKET_DIR={{ justfile_directory() + "./cloudsql"}}
  # ./run_app.py
  # sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain tmp-certs/cert.pem
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
  just tf apply -auto-approve -var='cloud_run_container_image={{ gcr_image_name }}'
