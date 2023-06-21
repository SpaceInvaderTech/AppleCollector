#!/usr/bin/env zsh

brew update
brew upgrade
brew install python@3
pip3 install -U pip
pip3 install -r requirements.txt
