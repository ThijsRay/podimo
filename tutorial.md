<div align="center">

# Step by step beginners tutorial

Welcome, this is a tutorial for absolute beginners. If you have no previous experience with hosting a server, or working with a Raspberry Pi, this is for you. If you have any questions along the way, feel free to ask for help in our [Telegram community](https://t.me/+fhbeYgPzKU44MzVk).
</div>

## If you do not yet have a working Raspberry Pi
1. Flash Raspbian to your Pi. The [Raspberry Pi Imager](https://www.raspberrypi.com/software/) tool works well. Make sure to enable SSH if you don't have a display to connect your Pi to. For the remainder of this tutorial we'll assume you're logging into your Pi via SSH. Also make sure to set a login and password.
2. Connect your Pi to power and wifi/ethernet.

### Connecting, logging in & installing
3. In your router, assign a static IP-address to your Pi. How this works is different for every router so you'll have to figure this one out yourself.
4. Log into your Pi by opening a terminal and entering the following, followed by your password (this remains hidden).

```sh
ssh yourusername@theIP-addressofyourpi
```

5. Enter the following commands one by one to install the tool.

```sh
sudo apt-get update && sudo apt-get upgrade -y
sudo apt-get install git libxml2-dev libxslt-dev python3-venv -y
git clone https://github.com/ThijsRay/podimo
cd podimo
sudo python3 -m venv env
source env/bin/activate
sudo chmod -R a+rwx env
pip install -r requirements.txt
```

### Finetuning your configuration
6. Good work! Now go to [ScraperAPI](https://scraperapi.com) and create a free account. After signing up you'll immediately see an API key. Copy this for later use.
7. Enter the following:

```sh
sudo nano .env
```

8. An empty text editor now opens. Go to [this example file](https://github.com/ThijsRay/podimo/blob/main/.env.example) and copy the contents into the empty file. Now we'll change a few things.
9. Under GENERAL SETTINGS:

PODIMO_HOSTNAME= should be followed by your public IP-address (which you can find [here](https://whatismyipaddress.com)). It should look like this:

```sh
PODIMO_HOSTNAME="YOURPUBLICIP:12104"
```

PODIMO_BIND_HOST= you should change to the following:

```sh
PODIMO_BIND_HOST="0.0.0.0:12104"
```

10. Under PROXIES, remove the # in front of 3. SCRAPER_API

Remove the # in front of SCRAPER_API and add the api key you copied earlier between the "".

11. Hit ctrl-x, followed by y to save and close the file.

### Starting the tool
12. Type the following:

```sh
sudo nano /etc/systemd/system/podimo.service
```

12. Again an empty file will open. Paste the following into this file:

```sh
[Unit]
Description=Podimo Service
After=network.target

[Service]
Type=simple
User=YOUR_USERNAME
Group=YOUR_USERNAME
WorkingDirectory=/home/YOUR_USERNAME/podimo
EnvironmentFile=/home/YOUR_USERNAME/podimo/.env
ExecStart=/home/YOUR_USERNAME/podimo/env/bin/python /home/YOUR_USERNAME/podimo/main.py
Restart=always
LimitNOFILE=infinity

[Install]
WantedBy=multi-user.target
```

13. Replace in all five spots YOUR_USERNAME with your own username. You know, the name you chose at step 1.
14. Hit ctrl-x, followed by y to save and close the file.
15. Enter the following commands:

```sh
sudo chmod 644 /etc/systemd/system/podimo.service
sudo systemctl daemon-reload
sudo systemctl enable podimo.service
sudo systemctl start podimo.service
```

Done! If all went well you can now enter your local IP-address:12104 into your browser and it'll show your tool.

### A few smart things to end this tutorial
16. Enable port forwarding to the external 12104 port on your router. This enables you to use the tool when you're not home.
17. If you encounter problems and ask the community for help, they'll probably ask for logs. You can find these by entering one of the the following:

```sh
sudo journalctl -u podimo.service --since "1 hour ago”
sudo journalctl -u podimo.service --since "1 day ago”
```

18. If you want to update the tool, type the following while being in the /podimo folder:

```sh
git pull
```

# Support
If you find this tool to be helpful, please consider buying me a coffee! It is greatly appreciated!

<a href="https://www.buymeacoffee.com/thijsr"><img src="https://img.buymeacoffee.com/button-api/?text=Buy me a coffee&emoji=&slug=thijsr&button_colour=BD5FFF&font_colour=ffffff&font_family=Poppins&outline_colour=000000&coffee_colour=FFDD00" /></a>
