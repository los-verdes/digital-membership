tf_subdir      := "./terraform"
tfvars_file    := "lv-digital-membership.tfvars"

set-tf-ver-output:
  echo "::set-output name=terraform_version::$(cat {{ tf_subdir }}/.terraform-version)"

run-tf CMD:
  terraform -chdir="{{ justfile_directory() + "/" + tf_subdir }}" \
    {{ CMD }} \
    {{ if CMD != "init" { "-var-file=../" + tfvars_file } else { "" } }}

tf-init:
  just run-tf init

tf-auto-apply: tf-init
  just run-tf 'apply -auto-approve'
