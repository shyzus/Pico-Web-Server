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
import adafruit_logging as logging
from adafruit_ticks import ticks_ms, ticks_add, ticks_less

LICENSE_PATH = "/sd/LICENSE"
SECRETS_PATH = "/sd/secrets.json"
SECRETS = None
SSID = "ESP32"
PSK = "ESP32PICO"

a_pin = digitalio.DigitalInOut(board.GP12)
a_pin.direction = digitalio.Direction.INPUT
a_pin.pull = digitalio.Pull.UP

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
            shutdown_procedure()
        except KeyError as e:
            logger.error(f"Failed to find key in secrets! Key: {e}")
            shutdown_procedure()
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

def a_button_pressed():
    return not a_pin.value

def shutdown_procedure():
    logger.info("Shutting down...")
    fileHandler.close()
    storage.umount(vfs)
    sys.exit()

while True:
    try:
        fileHandler.stream.flush()
        shutdown = False
        if a_button_pressed():
            deadline = ticks_add(ticks_ms(), 5000)
            while ticks_less(ticks_ms(), deadline):
                if not a_button_pressed():
                    shutdown = False
                    break
                else:
                    shutdown = True
        if shutdown:
            shutdown_procedure()
            
        wsgiServer.update_poll()
        led.value=False
        # Could do any other background tasks here, like reading sensors
    except (ValueError, RuntimeError) as e:
        logger.error(f"Failed to update server, restarting ESP32\n {e}")
        fileHandler.close()
        storage.umount(vfs)
        wifi.reset()
        continue
    except ConnectionError as e:
        logger.error(f"Connection Error: {e}")
        continue
