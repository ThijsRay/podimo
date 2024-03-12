<div align="center">

# Step by step beginners tutorial

Welcome, this is a tutorial for absolute beginners. If you have no previous experience with hosting a server, or working with a Raspberry Pi, this is for you. If you have any questions along the way, feel free to ask for help in our [Telegram community](https://t.me/+fhbeYgPzKU44MzVk).
</div>

## If you do not yet have a working Raspberry Pi
1. Flash Raspbian to your Pi. The [Raspberry Pi Imager](https://www.raspberrypi.com/software/) tool works well. Make sure to enable SSH if you don't have a display to connect your Pi to. For the remainder of this tutorial we'll assume you're logging into your Pi remotely via SSH. Also make sure to set a login and password.
2. Connect your Pi to power and wifi/ethernet.

### Connecting, logging in & installing
3. In your router, assign a static IP-address to your Pi. How this works is different for every router so you'll have to figure this one out yourself.
4. Log into your Pi by opening a terminal and entering the following, followed by your password (this remains hidden).

```sh
ssh yourusername@theIP-addressofyourpi
```

5. Enter the following commands one by one to prepare your Pi for installing the tool. Don't worry if you get a notification that something is already installed; that's a good thing.

```sh
sudo apt-get update && sudo apt-get upgrade -y
sudo apt-get install git libxml2-dev libxslt-dev python3-venv -y
export EDITOR=nano
```

6. Now follow step 1 and 2 from the README file, which can be found [here](https://github.com/ThijsRay/podimo)

### Finetuning your configuration before launch
7. Good work! Now go to [ScraperAPI](https://scraperapi.com) and create a free account. After signing up you'll immediately see an API key. Copy this for later use.

8. Enter the following:

```sh
make config
```

9. An text editor now opens. We're changing a few things here.

10. Under GENERAL SETTINGS:

PODIMO_HOSTNAME= should be followed by your public IP-address (which you can find [here](https://whatismyipaddress.com)). It should look like this:

```sh
PODIMO_HOSTNAME="YOURPUBLICIP:12104"
```

PODIMO_BIND_HOST= you should change to the following:

```sh
PODIMO_BIND_HOST="0.0.0.0:12104"
```

12. Under PROXIES, remove the # in front of SCRAPER_API= and add the api key you copied earlier between the "".

13. Hit ctrl-x, followed by y to save and close the file.

### Starting the tool
14. Type the following:

```sh
make start
```


Done! If all went well you can now enter YOURIPADDRESS:12104 into your browser and it'll show your tool.

### A few smart things to end this tutorial
15. Enable port forwarding to the external 12104 port on your router. This enables you to use the tool when you're not home.

16. If you encounter problems and ask the community for help, they'll probably ask for logs. You can find these by entering one of the the following:

```sh
make logs
```

17. If you want to update the tool, type the following while being in the /podimo folder:

```sh
make update
```

# Support
If you find this tool to be helpful, please consider buying me a coffee! It is greatly appreciated!

<a href="https://www.buymeacoffee.com/thijsr"><img src="https://img.buymeacoffee.com/button-api/?text=Buy me a coffee&emoji=&slug=thijsr&button_colour=BD5FFF&font_colour=ffffff&font_family=Poppins&outline_colour=000000&coffee_colour=FFDD00" /></a>
