#!/bin/bash

set -eou pipefail
SECRET="D2A829A37C01631F35CB202B394826A654A4177EB1B1FB698482AA632D623AF2"
WEBSITE_ID="620c2c763b1f5c0f1b713afe"
WEBHOOK_ID="45f9d20d-ac62-4dbe-816b-b86ab0bbf69a"
# WEBHOOK_PAYLOAD='{"createdOn":"2022-02-17T21:29:51.705796Z","data":{"orderId":"test-order-id"},"id":"e61d6232-8c85-4b7b-9bf2-174544c2a1c5","subscriptionId":"'"$WEBHOOK_ID"'","topic":"order.create","websiteId":"'"$WEBSITE_ID"'"}'
WEBHOOK_PAYLOAD='{"id":"5a3e1f71-3b85-401e-b58e-ae7ed3e3c41d","websiteId":"'"$WEBSITE_ID"'","subscriptionId":"'"$WEBHOOK_ID"'","topic":"order.create","data":{"orderId":"test-order-id"},"createdOn":"2022-02-18T02:40:00.964528Z"}'
EXPECTED_SIGNATURE="$(echo -n "$WEBHOOK_PAYLOAD" | openssl sha256 -mac hmac -macopt hexkey:$SECRET | tr '[:lower:]' '[:upper:]')"
SIGNATURE="5F17D23002AD1E31C87DF36DF5CF1B130CDFF0D7A314B47F0A1C5647CF88D144"

echo "EXPECTED_SIGNATURE:"
echo "$EXPECTED_SIGNATURE"
echo "SIGNATURE:"
echo "$SIGNATURE"
[[ "$EXPECTED_SIGNATURE" == "$SIGNATURE" ]]
# TEST_CARD_JSON="$(\
#   echo "SELECT json_agg(m) FROM membership_cards as m;" \
#     | psql "postgresql://member-card-user:member-card-password@127.0.0.1:5433/digital-membership" \
#     | tail -n +3 \
#     | perl -pe 'chomp if eof' \
#     | sed '$ d' \
#     | jq -r '.[]' \
# )"
# echo "TEST_CARD_JSON: $TEST_CARD_JSON"

curl -v \
  -H "Squarespace-Signature: $SIGNATURE" \
  -H 'Content-Type: application/json' \
  -d "$WEBHOOK_PAYLOAD" \
  "https://localcard.losverd.es:5000/squarespace/order-webhook"
