#!/usr/bin/env zsh
#
set -ue -o pipefail

ENV_FILES=(
    env.rc
    environments/development/sites/sibook.local/env.rc
    environments/production/sites/sibook.local/env.rc
)

MERGED_ENV_FILE=".env"

>&2 print "Merging env files: ${(j:\n:)ENV_FILES} to '$MERGED_ENV_FILE'"
cat $ENV_FILES > $MERGED_ENV_FILE
docker compose --env-file=$MERGED_ENV_FILE up
