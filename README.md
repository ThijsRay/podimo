<div align="center">

# Podimo to RSS

Podimo is a proprietary podcasting player that enables you to listen to various exclusive shows behind a paywall.
This tool allows you to stream Podimo podcasts with your preferred podcast player, without having to use the Podimo app.
</div>

## Recommended installation for self-hosting
Make sure you have a recent Python 3 version installed, as this is required for the steps below.

1. Clone this repository and enter the newly created directory
```sh
git clone https://github.com/ThijsRay/podimo
cd podimo
```

2. Get the latest update and install it as a service with
```sh
make update
make install
```

3. Run the program with
```sh
make start
```

4. Visit http://localhost:12104. You should see the site now! If you want to reach it from
other machines, make sure to edit the configuration with
```sh
make config
```
A complete list of all configuration options can be found in the [.env.example file](.env.example)

## Instructions for self-hosting with Docker

1. Clone this repository and enter the newly created directory
```sh
git clone https://github.com/ThijsRay/podimo
cd podimo
```

2. Build the Docker image
```sh
docker build -t podimo:latest .
```

3. Run the Docker image.
Make sure you set the correct environment variables if you want to configure any variables.
See [.env.example](.env.example) for a full list
of configuration options.
```sh
docker run --rm -e PODIMO_BIND_HOST=0.0.0.0:12104 -p 12104:12104 -v $(pwd)/cache:/src/cache podimo:latest
```

4. Visit http://localhost:12104. You should see the site now!

## Configuration
A complete list of all configuration options can be found in the [.env.example file](.env.example)

## Bot detection
Depending on your usage patterns, it might be necessary to bypass Podimo's anti-bot mechanisms.
This can be done through a Zenrows, ScraperAPI or a generic HTTP proxy.

### Setting up a Zenrows account
You can create a free trial account for Zenrows

1. Go to [app.zenrows.com/register](https://app.zenrows.com/register) and create a free account
2. Copy your API key and make sure to add it to the `ZENROWS_API` environment variable

### Setting up a ScraperAPI account
You can create a free trial account for ScraperAPI

1. Go to [dashboard.scraperapi.com/signup](https://dashboard.scraperapi.com/signup) and create a free account
2. Copy your API key and make sure to add it to the `SCRAPER_API` environment variable

## Privacy
The script keeps track of a few things in memory:
- Your username and password, used to login and to create an access token. This is only used temporarily during a request itself.
- A cryptographic hash that is calculated based on your username and password.
- A Podimo access token, which is kept in memory for accessing pages after logging in.

This data is not written to the disk (unless `STORE_TOKENS_ON_DISK` is set to true) and it is _never_ logged.

# License
```
Copyright 2022-2023 Thijs Raymakers

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
