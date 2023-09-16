import board
import busio
import digitalio
import adafruit_sdcard
import storage
import os
import json
import sys
import time

import staticWSGIApplication as StaticWSGIApplication

import adafruit_requests as requests
from adafruit_esp32spi import adafruit_esp32spi
import adafruit_esp32spi.adafruit_esp32spi_wifimanager as wifimanager

import adafruit_wsgi.esp32spi_wsgiserver as server
from adafruit_wsgi.wsgi_app import WSGIApp

import adafruit_logging as logging

LICENSE_PATH = "/sd/LICENSE"
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

logger = logging.getLogger("default")
logger.setLevel(logging.INFO)

time_struct = time.localtime(time.time())

fileHandler = logging.FileHandler(f"/sd/logs/{time_struct.tm_year}_{time_struct.tm_mon}_{time_struct.tm_mday}-{time_struct.tm_hour}_{time_struct.tm_min}.log", "a")
streamHandler = logging.StreamHandler(sys.stdout)

logger.addHandler(fileHandler)
logger.addHandler(streamHandler)

try:
    with open(LICENSE_PATH) as f:
        logger.info(f.read())
except Exception as e:
    logger.error(e)    

try:
    with open(SECRETS_PATH) as f:
        try:
            SECRETS = json.load(f)
            SSID = SECRETS["SSID"]
            PSK = SECRETS["PSK"]
        except ValueError as e:
            logger.error(f"Malformed secrets! {e}")
            fileHandler.close()
            sys.exit()
        except KeyError as e:
            logger.error(f"Failed to find key in secrets! Key: {e}")
            fileHandler.close()
            sys.exit()
except OSError:
    logger.error(f"{SECRETS_PATH} ,not found! Using default SSID/PSK to setup AP!")
    logger.info(f"SSID: {SSID}, PSK: {PSK}")

wifi = wifimanager.ESPSPI_WiFiManager(esp, {"ssid":SSID,"password":PSK}, debug=True)

if SECRETS is None:
    wifi.create_ap()
else:
    wifi.connect()
    
ip = esp.pretty_ip(esp.network_data["ip_addr"])
logger.info(ip)

web_app = StaticWSGIApplication.StaticWSGIApplication(static_dir="/sd/web", debug=True)

server.set_interface(esp)
wsgiServer = server.WSGIServer(80, application=web_app, debug=True)
wsgiServer.start()

while True:
    try:
        fileHandler.stream.flush()
        wsgiServer.update_poll()
        led.value=False
        # Could do any other background tasks here, like reading sensors
    except (ValueError, RuntimeError) as e:
        logger.error(f"Failed to update server, restarting ESP32\n {e}")
        filehHandler.close()
        storage.umount(vfs)
        wifi.reset()
        continue
    except ConnectionError as e:
        logger.error(f"Connection Error: {e}")
        continue
