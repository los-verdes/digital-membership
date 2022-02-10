#!/bin/bash
SERIAL_NUM="204155103484615837705374825908876627803"
AUTH_TOKEN="Fg3O4R091QTtfJQMQcGKNg-LGFgfCj8vPeD_ikc8g0c="
TEST_CARD_JSON="$(\
  echo "SELECT json_agg(m) FROM membership_cards as m;" \
    | psql "postgresql://member-card-user:member-card-password@127.0.0.1:5433/digital-membership" \
    | tail -n +3 \
    | perl -pe 'chomp if eof' \
    | sed '$ d' \
    | jq -r '.[]' \
)"
echo "TEST_CARD_JSON: $TEST_CARD_JSON"

curl -v \
  -H "Authorization: ApplePass $AUTH_TOKEN" \
  -d 'pushToken=jhog-test' \
  "https://localcard.losverd.es:5000/passkit/v1/devices/jhog-test/registrations/pass.es.losverd.card/$SERIAL_NUM"

echo -e '\n\n'; read -pr "Press any key to resume ..."

curl -v \
  -H "Authorization: ApplePass $AUTH_TOKEN" \
  "https://localcard.losverd.es:5000/passkit/v1/devices/jhog-test/registrations/pass.es.losverd.card"

echo -e '\n\n'; read -pr "Press any key to resume ..."

curl -v \
  -H 'if-MODified-Since: 2020-04-05' \
  -H "Authorization: ApplePass $AUTH_TOKEN" \
  "https://localcard.losverd.es:5000/passkit/v1/passes/pass.es.losverd.card/$SERIAL_NUM"



echo -e '\n\n'; read -pr "Press any key to resume ..."

curl -v \
  -H 'If-Modified-Since: 2022-04-05' \
  -H "Authorization: ApplePass $AUTH_TOKEN" \
  "https://localcard.losverd.es:5000/passkit/v1/passes/pass.es.losverd.card/$SERIAL_NUM"



echo -e '\n\n'; read -pr "Press any key to resume ..."

curl -v \
  -H "Authorization: ApplePass $AUTH_TOKEN" \
  -X DELETE \
  "https://localcard.losverd.es:5000/passkit/v1/devices/jhog-test/registrations/pass.es.losverd.card/$SERIAL_NUM"
