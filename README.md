# Pico Web Server

A simple Raspberry Pi Pico powered web server using CircuitPython.

# Hardware
Raspberry Pi Pico with headers and a [Pico Wireless Pack](https://shop.pimoroni.com/products/pico-wireless-pack) by Pimoroni.

Any microcontroller will do considering it has matching pinouts to the pico and headers to connect to the other components. Given that the Pico Wireless Pack is discontinued at the time of writing it is possible to use an ESP32 that is compatible with [adafruit_esp32_spi](https://docs.circuitpython.org/projects/esp32spi/en/latest/api.html#module-adafruit_esp32spi.adafruit_esp32spi) library.

This web server uses an SD Card for the storage for most of its data. Any microSD card and reader compatible with [adafruit_sdcard](https://github.com/adafruit/Adafruit_CircuitPython_SD).

# Software
CircuitPython is required for this project to function.
Make sure to flash your pico using the [Adafruit website](https://circuitpython.org/board/raspberry_pi_pico/).
