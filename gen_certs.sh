#!/bin/bash

set -exou pipefail

openssl genrsa 2048 > ./tmp-certs/ca-key.pem
openssl req -new -x509 -nodes -days 365 \
  -subj "/CN=losverd.es" \
  -key ./tmp-certs/ca-key.pem \
  -out ./tmp-certs/ca-cert.pem

# Then generate flask certificate key and CSR
openssl req \
  -subj "/CN=localcerts.losverd.es" \
  -newkey rsa:2048 -nodes \
  -keyout ./tmp-certs/flask-key.pem \
  -out ./tmp-certs/flask-req.csr

cat << CONF > ./tmp-certs/cert.conf
[dn]
CN=crt-github-runners.ci-vault.hashicorp.services
[req]
distinguished_name = dn
prompt = no
[v3_req]
subjectAltName=IP:127.0.0.1,DNS:localcard.losverd.es
keyUsage=digitalSignature
extendedKeyUsage=serverAuth
CONF

# Next, the actual flask certificate generation
# (by default lasts 1 month after creation)
openssl x509 -req \
  -extfile ./tmp-certs/cert.conf \
  -extensions v3_req \
  -CAcreateserial \
  -CA ./tmp-certs/ca-cert.pem \
  -CAkey ./tmp-certs/ca-key.pem \
  -in ./tmp-certs/flask-req.csr \
  -out ./tmp-certs/flask-cert.pem

sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain ./tmp-certs/ca-cert.pem
