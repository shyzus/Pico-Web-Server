import board
import busio
import digitalio
import adafruit_sdcard
import storage
import os
import json
import sys
import time
import math
import supervisor

import staticWSGIApplication as StaticWSGIApplication

import adafruit_requests as requests
from adafruit_esp32spi import adafruit_esp32spi
import adafruit_esp32spi.adafruit_esp32spi_wifimanager as wifimanager
import adafruit_wsgi.esp32spi_wsgiserver as server
import adafruit_logging as logging
from adafruit_ticks import ticks_ms, ticks_add, ticks_less

SECRETS = {
    "ssid": os.getenv("CIRCUITPY_WIFI_SSID"),
    "password": os.getenv("CIRCUITPY_WIFI_PASSWORD"),
}

LICENSE_PATH = "/sd/LICENSE"
SSID = "ESP32"
PSK = "ESP32PICO"
PIMO_RED_PIN = 25
PIMO_GREEN_PIN = 26
PIMO_BLUE_PIN = 27

a_pin = digitalio.DigitalInOut(board.GP12)
a_pin.direction = digitalio.Direction.INPUT
a_pin.pull = digitalio.Pull.UP

spi = busio.SPI(board.GP18, board.GP19, board.GP16)
cs = digitalio.DigitalInOut(board.GP22)
sdcard = adafruit_sdcard.SDCard(spi, cs)
vfs = storage.VfsFat(sdcard)
storage.mount(vfs, "/sd")

esp32_cs = digitalio.DigitalInOut(board.GP7)
esp32_ready = digitalio.DigitalInOut(board.GP10)
esp32_reset = digitalio.DigitalInOut(board.GP11)
esp = adafruit_esp32spi.ESP_SPIcontrol(spi, esp32_cs, esp32_ready, esp32_reset)

# values between 0 and 1.0
# 1.0 means off
# 0 is full on
def set_pimo_led(red, green, blue):
    esp.set_analog_write(PIMO_RED_PIN, red )
    esp.set_analog_write(PIMO_GREEN_PIN, green)
    esp.set_analog_write(PIMO_BLUE_PIN, blue)

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

if SECRETS is None:
    wifi = wifimanager.ESPSPI_WiFiManager(esp, {'ssid': SSID, 'psk': PSK}, debug=True)
    wifi.create_ap()
else:
    wifi = wifimanager.ESPSPI_WiFiManager(esp, SECRETS, debug=True)
    wifi.connect()
    
ip = esp.pretty_ip(esp.network_data["ip_addr"])
logger.info(ip)

web_app = StaticWSGIApplication.StaticWSGIApplication(static_dir="/sd/web", debug=True)

def htmx_test(environ):
    status = "200 OK"
    headers = [("Content-type", "text/plain")]
    return (status, headers, ["YEEEEEEE"])

web_app.on("POST", "/clicked", htmx_test)

server.set_interface(esp)
wsgiServer = server.WSGIServer(80, application=web_app, debug=True)
wsgiServer.start()

def a_button_pressed():
    return not a_pin.value

def pico_button_pressed():
    return pico_pin.value

def shutdown_procedure():
    set_pimo_led(0.9,1,1)
    logger.info("Shutting down...")
    fileHandler.close()
    storage.umount(vfs)
    esp.disconnect()
    sys.exit()

shutdown = False

while True:
    try:
        set_pimo_led(1,0.9,1)
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
            
        set_pimo_led(1,1,1)
        wsgiServer.update_poll()
        # Could do any other background tasks here, like reading sensors
    except (ValueError, RuntimeError) as e:
        logger.error(f"Failed to update server, restarting ESP32\n {e}")
        fileHandler.close()
        storage.umount(vfs)
        wifi.reset()
        continue

    except ConnectionError as e:
        set_pimo_led(0.9,1,1)
        logger.error(f"Connection Error: {e}")
        continue
