#!/usr/bin/env zsh

HOSTNAME="api.example.com"
PATH="/signals"
ENDPOINT="https://$HOSTNAME$PATH"
MINUTES=15
HAYPATH="../haystacks"
PASSWD=$(<$HOME/.haypass)
CMD="./plist.py --path $HAYPATH --minutes $MINUTES --endpoint $ENDPOINT --key $PASSWD --verbose"

export USER_AGENT_COMMENT="I am @webjay"
export PATH=/opt/homebrew/bin:/usr/bin:/usr/local/bin:$PATH

eval "$(brew shellenv)"
eval "python3 $CMD"
