import board
import busio
import digitalio
import adafruit_sdcard
import storage
import os
import json
import sys

import adafruit_requests as requests
from adafruit_esp32spi import adafruit_esp32spi
import adafruit_esp32spi.adafruit_esp32spi_wifimanager as wifimanager

import adafruit_wsgi.esp32spi_wsgiserver as server
from adafruit_wsgi.wsgi_app import WSGIApp

HTML_BASE_DIR = "/sd/web/html"
SECRETS_PATH = "/sd/secrets.json"
SECRETS = None
SSID = "ESP32"
PSK = "ESP32PICO"

spi = busio.SPI(board.GP18, board.GP19, board.GP16)
cs = digitalio.DigitalInOut(board.GP22)
sdcard = adafruit_sdcard.SDCard(spi, cs)
vfs = storage.VfsFat(sdcard)
storage.mount(vfs, "/sd")

led = digitalio.DigitalInOut(board.LED)
led.direction = digitalio.Direction.OUTPUT

esp32_cs = digitalio.DigitalInOut(board.GP7)
esp32_ready = digitalio.DigitalInOut(board.GP10)
esp32_reset = digitalio.DigitalInOut(board.GP11)
esp = adafruit_esp32spi.ESP_SPIcontrol(spi, esp32_cs, esp32_ready, esp32_reset)

try:
    with open(SECRETS_PATH) as f:
        try:
            SECRETS = json.load(f)
            SSID = SECRETS["SSID"]
            PSK = SECRETS["PSK"]
        except ValueError as e:
            print("Malformed secrets!", e)
            sys.exit()
        except KeyError as e:
            print("Failed to find key in secrets! Key:", e)
            sys.exit()
except OSError:
    print(SECRETS_PATH,"not found! Using default SSID/PSK to setup AP!")
    print("SSID:", SSID, "PSK:", PSK)

html = {}
js = {}
css = {}

for file in os.listdir(HTML_BASE_DIR):
    if file.endswith(".html"):
        with open("".join([HTML_BASE_DIR, os.sep, file]), 'r') as f:
            html[file] = f.read()

wifi = wifimanager.ESPSPI_WiFiManager(esp, {"ssid":SSID,"password":PSK}, debug=True)

if SECRETS is None:
    wifi.create_ap()
else:
    wifi.connect()
    
ip = esp.pretty_ip(esp.network_data["ip_addr"])
print(ip)

web_app = WSGIApp()

@web_app.route("/")
def index(request):
    led.value=True
    return ("200 OK", [], html["index.html"])

server.set_interface(esp)
wsgiServer = server.WSGIServer(80, application=web_app, debug=True)
wsgiServer.start()
while True:
    try:
        wsgiServer.update_poll()
        led.value=False
        # Could do any other background tasks here, like reading sensors
    except (ValueError, RuntimeError) as e:
        print("Failed to update server, restarting ESP32\n", e)
        storage.umount(vfs)
        esp.reset()
        continue
    except ConnectionError as e:
        print("Connection Error:", e)
        continue
    except Exception as e:
        print("Exception:", e)
        storage.umount(vfs)
        sys.exit()
