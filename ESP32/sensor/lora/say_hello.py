from machine import Pin, SPI
from sx127x import SX127x
import time

# กำหนดขา (ตามที่คุณบอก)
# SCK:18, MISO:19, MOSI:23, CS:5, RST:25, DIO0:26
lora_pins = {
    'ss': Pin(5, Pin.OUT),
    'rst': Pin(25, Pin.OUT),
    'dio0': Pin(26, Pin.IN)
}

# ตั้งค่า LoRa (433MHz)
lora_params = {
    'frequency': 433000000,
    'bandwidth': 125000,
    'sf': 7,
    'cr': 5,
    'sync_word': 0x12,
    'preamble_length': 8
}

# เริ่มการทำงาน SPI
spi = SPI(1, baudrate=100,000, sck=Pin(18), mosi=Pin(23), miso=Pin(19))
lora = SX127x(spi, lora_pins, lora_params)

counter = 0

print("LoRa Sender Started")

while True:
    message = "Hello #{}".format(counter)
    print("Sending:", message)
    
    lora.send(message)
    
    counter += 1
    time.sleep(1) # ส่งทุก 1 วินาที