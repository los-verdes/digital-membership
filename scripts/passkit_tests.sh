#!/bin/bash

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
  -H 'Authorization: ApplePass 9d6DWsJHyHS9WXD97_FOu9sfXtyh1bPN1d0c3ZMeoik=' \
  -d 'pushToken=jhog-test' \
  'https://localcard.losverd.es:5000/passkit/v1/devices/jhog-test/registrations/pass.es.losverd.card/306545713186892282203418129365028161033'

echo -e '\n\n'; read -p "Press any key to resume ..."

curl -v \
  -H 'Authorization: ApplePass 9d6DWsJHyHS9WXD97_FOu9sfXtyh1bPN1d0c3ZMeoik=' \
  'https://localcard.losverd.es:5000/passkit/v1/devices/jhog-test/registrations/pass.es.losverd.card'

echo -e '\n\n'; read -p "Press any key to resume ..."

curl -v \
  -H 'if-MODified-Since: 2020-04-05' \
  -H 'Authorization: ApplePass 9d6DWsJHyHS9WXD97_FOu9sfXtyh1bPN1d0c3ZMeoik=' \
  'https://localcard.losverd.es:5000/passkit/v1/passes/pass.es.losverd.card/306545713186892282203418129365028161033'



echo -e '\n\n'; read -p "Press any key to resume ..."

curl -v \
  -H 'If-Modified-Since: 2022-04-05' \
  -H 'Authorization: ApplePass 9d6DWsJHyHS9WXD97_FOu9sfXtyh1bPN1d0c3ZMeoik=' \
  'https://localcard.losverd.es:5000/passkit/v1/passes/pass.es.losverd.card/306545713186892282203418129365028161033'



echo -e '\n\n'; read -p "Press any key to resume ..."

curl -v \
  -H 'Authorization: ApplePass 9d6DWsJHyHS9WXD97_FOu9sfXtyh1bPN1d0c3ZMeoik=' \
  -X DELETE \
  'https://localcard.losverd.es:5000/passkit/v1/devices/jhog-test/registrations/pass.es.losverd.card/306545713186892282203418129365028161033'
