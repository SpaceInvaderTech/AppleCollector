#!/usr/bin/env zsh

HEADERS='{"X-API-Key": "xyz"}'
STARTPOINT="https://api.example.com/start"
ENDPOINT="https://api.example.com/end"
PASSWD=$(<$HOME/.haypass)
CMD="./main.py --headers $HEADERS --startpoint $STARTPOINT --endpoint $ENDPOINT --key $PASSWD"

export USER_AGENT_COMMENT="I am @webjay"
export PATH=/opt/homebrew/bin:/usr/bin:/usr/local/bin:$PATH

eval "$(brew shellenv)"
eval "python3 $CMD"
