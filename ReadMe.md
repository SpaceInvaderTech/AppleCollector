# AppleCollector

Query Apple's Find My network, based on all the hard work of [OpenHaystack](https://github.com/seemoo-lab/openhaystack/) and @vtky and @hatomist and others.

This is a fork of great work from @biemster and modified to have device locations sent to an endpoint.

## Prerequisites

XCode or Command Line Tools, latest pip (`pip3 install -U pip`, otherwise `cryptography` will not install).

    pip3 install -r requirements.txt

## Scripts

`plist.py` will query Apple's Find My network based on Property Lists files exported from OpenHaystack and can send locations to an endpoint.

    ./plist.py --path hay/stack --minutes 15 --endpoint https://api.example.com/post --verbose

`passwd.sh` will get a one time password for iCloud and store it in `$HOME/.haypass`.

`example.cron.sh` is an example script for running `plist.py`.

`launched.AppleCollector.plist` is for periodically running `cron.sh`.

Setup:

    mkdir -p ~/Library/LaunchAgents
    cp launched.AppleCollector.plist ~/Library/LaunchAgents/
    launchctl load -w ~/Library/LaunchAgents/launched.AppleCollector.plist
