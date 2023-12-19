SHELL := bash
.ONESHELL:
.SHELLFLAGS := -eu -o pipefail -c
.DELETE_ON_ERROR:
MAKEFLAGS += --warn-undefined-variables
MAKEFLAGS += --no-builtin-rules

VENV=venv/bin/activate

help:
	@echo "The following options are available:"
	echo -e "\$$ make update"
	echo -e "\tUpdate the tool to the latest release"
	echo -e "\$$ make help"
	echo -e "\tDisplay this help menu"
.PHONY: help

update: VENV
	@echo "Fetching latest releases..."
	git fetch --tags
	export GIT_TAG="$$(git describe --abbrev=0 --tags)"
	echo "Checkout out to latest release $$GIT_TAG"
	git checkout "$$GIT_TAG"
	echo "Updating dependencies..."
	source venv/bin/activate
	pip install -r requirements.txt
	echo "Updated to version $$GIT_TAG"
	git diff --name-only --no-index -- .env.example .env >/dev/null ||
	(echo -e "\n#############################################################"
	 echo -e   "# Your config differs from example config in .env.example!  #"
	 echo -e   "# This is not an issue, but new configuration options might #"
	 echo -e 	 "# not yet be present in your .env file.                     #"
	 echo -e 	 "#                                                           #"
	 echo -e 	 "#            The differences are shown below                #"
	 echo -e   "#############################################################\n")
	(git diff --no-index -- .env.example .env || true)
.PHONY: update

config: .env
	@$$EDITOR .env

.env:
	cp .env.example .env

VENV:
	python -m virtualenv venv --prompt podimo
