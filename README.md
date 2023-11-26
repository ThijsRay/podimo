<div align="center">

# Podimo to RSS

Podimo is a proprietary podcasting player that enables you to listen to various exclusive shows behind a paywall.
This tool allows you to stream Podimo podcasts with your preferred podcast player, without having to use the Podimo app.

</div>

## Usage

The easiest way to use it is via [podimo.thijs.sh](https://podimo.thijs.sh). You can also host it yourself by following the instructions below. It's necessary to create a ScraperAPI account to bypass Podimo's anti-bot mechanisms.

## Setting up a ScraperAPI account

You can create a free account, which gives you 1000 free API credits per month.

1. Go to [dashboard.scraperapi.com/signup](https://dashboard.scraperapi.com/signup) and create a free account
2. Copy your API key and make sure to add it to the `SCRAPER_API` environment variable (`-e`) in the Docker run command

## Instructions for self-hosting (with Docker)

1. Clone this repository and enter the newly created directory

```sh
git clone https://github.com/ThijsRay/podimo
cd podimo
```

2. Build the Docker image

```sh
docker build -t podimo:latest .
```

3. Run the Docker image

```sh
docker run --rm -e PODIMO_HOSTNAME=yourip:12104 -e PODIMO_BIND_HOST=0.0.0.0:12104 -e PODIMO_PROTOCOL=http -e SCRAPER_API=APIKEY -p 12104:12104 podimo:latest
```

For an explaination of what each environmental variable (`-e`) does, see the section on [configuration with environmental variables](#configuration).

4. Visit http://yourip:12104. You should see the site now!

## Installation for self-hosting (without Docker)

Make sure you have a recent Python 3 version installed, as this is required for the steps below.

1. Clone this repository and enter the newly created directory

```sh
git clone https://github.com/ThijsRay/podimo
cd podimo
```

2. (Optional) Create a virtual environment to install the Python packages in

```sh
vitualenv venv
source venv/bin/activate
```

3. Install the required packages with

```sh
pip install -r requirements.txt
```

4. Run the program with

```sh
python main.py
```

4. Visit http://localhost:12104. You should see the site now!

## Configuration

There are a few environmental variables that can configure this tool

- `PODIMO_HOSTNAME` Sets the hostname that is displayed in the interface to a custom value, defaults to `podimo.thijs.sh`
- `PODIMO_BIND_HOST` Sets the IP and port to which this tool should bind, defaults to `127.0.0.1:12104`.
- `PODIMO_PROTOCOL` Sets the protocol that is displayed in the interface. For local
  deployments it can be useful to set this to `http`. Defaults to `https`.
- `ZENROWS_API` Sets the Zenrows API key for it to be used.
- `DEBUG` Shows a bit more information that can be useful while debugging
- `HTTP_PROXY` A URL for an HTTP proxy that can be used to rotate IP addresses to avoid being blocked by CloudFlare.

Other configuration values can be found in `podimo/config.py`, but they generally don't have to be changed.

## Privacy

The script keeps track of a few things in memory:

- Your username and password, used to login and to create an access token. This is only used temporarily during a request itself.
- A cryptographic hash that is calculated based on your username and password.
- A Podimo access token, which is kept in memory for accessing pages after logging in.

This data is _never_ written to the disk and it is _never_ logged. The hosted script on [podimo.thijs.sh](https://podimo.thijs.sh) runs behind an `nginx` reverse proxy that requires HTTPS and does not keep any logs. The `nginx` configuration is:

```nginx
limit_req_zone $binary_remote_addr zone=podimo_limit:10m rate=1r/s;
server {
	server_name podimo.thijs.sh;
	access_log off;
	error_log   /dev/null   crit;

	location / {
		proxy_pass http://127.0.0.1:12104;

		limit_req zone=podimo_limit burst=5;
		limit_req_status 429;

		add_header Strict-Transport-Security "max-age=31536000;" always;

		add_header Cache-Control "public, max-age=300";
		add_header X-Accel-Buffering no;
		proxy_buffering off;

		proxy_set_header X-Real-IP $remote_addr;
	}

	listen [::]:443 ssl ipv6only=on;
	listen 443 ssl;
	ssl_certificate /etc/letsencrypt/live/podimo.thijs.sh/fullchain.pem;
	ssl_certificate_key /etc/letsencrypt/live/podimo.thijs.sh/privkey.pem;
	include /etc/letsencrypt/options-ssl-nginx.conf;
	ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;
}


server {
	if ($host = podimo.thijs.sh) {
		return 301 https://$host$request_uri;
	}

	access_log off;
	listen 80;
	listen [::]:80;
	server_name podimo.thijs.sh;
	return 404;
}
```

# License

```
Copyright 2022 Thijs Raymakers

Licensed under the EUPL, Version 1.2 or – as soon they
will be approved by the European Commission - subsequent
versions of the EUPL (the "Licence");
You may not use this work except in compliance with the
Licence.
You may obtain a copy of the Licence at:

https://joinup.ec.europa.eu/software/page/eupl

Unless required by applicable law or agreed to in
writing, software distributed under the Licence is
distributed on an "AS IS" basis,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either
express or implied.
See the Licence for the specific language governing
permissions and limitations under the Licence.
```

# Support

If you find this tool to be helpful, please consider buying me a coffee! It is greatly appreciated!

<a href="https://www.buymeacoffee.com/thijsr"><img src="https://img.buymeacoffee.com/button-api/?text=Buy me a coffee&emoji=&slug=thijsr&button_colour=BD5FFF&font_colour=ffffff&font_family=Poppins&outline_colour=000000&coffee_colour=FFDD00" /></a>
