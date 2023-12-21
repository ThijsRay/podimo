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
	echo -e "\tUpdate the tool to the latest release\n"
	echo -e "\$$ make config"
	echo -e "\tEdit configuration options for the tool\n"
	echo -e "\$$ make start"
	echo -e "\$$ make restart"
	echo -e "\$$ make stop"
	echo -e "\tChange the state of the tool, assuming it has been\n\tinstalled as a service\n"
	echo -e "\$$ make install"
	echo -e "\$$ make uninstall"
	echo -e "\t(Un)install the tool as a service\n"
	echo -e "\$$ make status"
	echo -e "\$$ make logs"
	echo -e "\tView the current status and/or logs\n"
	echo -e "\$$ make help"
	echo -e "\tDisplay this help menu"
.PHONY: help

update: VENV
	@export CURRENT_GIT_TAG="$$(git describe --abbrev=0 --tags)"
	echo "Current version is $$CURRENT_GIT_TAG"
	echo "Fetching latest releases..."
	git fetch --tags
	export UPDATE_GIT_TAG="$$(git describe --tags $$(git rev-list --tags --max-count=1))"
	if [[ "$$CURRENT_GIT_TAG" == "$$UPDATE_GIT_TAG" ]]; then
		echo "Already on the latest release $$CURRENT_GIT_TAG!"
		exit 0
	fi
	echo "Checkout out to latest release $$UPDATE_GIT_TAG"
	git checkout "$$UPDATE_GIT_TAG"
	echo "Updating dependencies..."
	source venv/bin/activate
	pip install -r requirements.txt
	echo "Updated to version $$UPDATE_GIT_TAG"
	if test -f ".env"; then
		if test -r ".env"; then
			git diff --name-only --no-index -- .env.example .env >/dev/null ||
			(echo -e "\n#############################################################"
			 echo -e   "# Your config differs from example config in .env.example!  #"
			 echo -e   "# This is not an issue, but new configuration options might #"
			 echo -e 	 "# not yet be present in your .env file.                     #"
			 echo -e 	 "#                                                           #"
			 echo -e 	 "#            The differences are shown below                #"
			 echo -e   "#############################################################\n")
			(git diff --no-index -- .env.example .env || true)
		else
			echo ".env file exists, but cannot be read"
			exit 1
		fi
	fi
.PHONY: update

config: .env
	@# Use the editor specified in the EDITOR environment variable,
	@# or default to nano otherwise.
	@which $$EDITOR &>/dev/null || export EDITOR=nano
	which $$EDITOR &>/dev/null || echo "Unable to find the nano binary. Either set the EDITOR environment variable to an editor of your choice or install nano"
	read -e -p "You will open the config file .env in the editor $$EDITOR. Continue? [Y/n]> "
	[[ "$$REPLY" != [nN]* ]] && $$EDITOR .env || exit 1
	echo "Make sure to restart the service with \"make restart\" to apply the changes!"

.env:
	cp .env.example .env

start:
	sudo systemctl enable --now podimo.service
.PHONY: start

restart:
	sudo systemctl restart podimo.service
.PHONY: restart

stop:
	sudo systemctl disable --now podimo.service
.PHONY: stop

status:
	sudo systemctl status podimo.service
.PHONY: status

logs:
	sudo journalctl -f --since today -u podimo.service
.PHONY: logs

install:
	@cat > .podimo.service <<EOL
	# This is managed by $$(pwd)/Makefile
	[Unit]
	Description=Podimo to RSS converter
	After=network.target
	 
	[Service]
	Type=simple
	User=$$(id -un)
	Group=$$(id -gn)
	WorkingDirectory=$$(pwd)
	ExecStart=$$(pwd)/venv/bin/python main.py
	Restart=always
	LimitNOFILE=infinity
	 
	[Install]
	WantedBy=multi-user.target
	EOL
	chmod 644 .podimo.service
	sudo cp .podimo.service /etc/systemd/system/podimo.service
	rm -rf .podimo.service
	sudo systemctl daemon-reload
	sudo systemctl enable podimo.service
	echo "Installed service! It will run as user $$(id -un) and group $$(id -gn)"
.PHONY: install

uninstall: stop
	sudo rm -rf /etc/systemd/system/podimo.service
	sudo systemctl daemon-reload
.PHONY: uninstall

VENV:
	python -m venv venv --prompt podimo
