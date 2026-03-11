from machine import Pin, SPI
from sx127x import SX127x
import time

# กำหนดขาเหมือนกัน
lora_pins = {
    'ss': Pin(5, Pin.OUT),
    'rst': Pin(25, Pin.OUT),
    'dio0': Pin(26, Pin.IN)
}

# ตั้งค่าให้ตรงกับตัวส่งเป๊ะๆ
lora_params = {
    'frequency': 433000000,
    'bandwidth': 125000,
    'sf': 7,
    'cr': 5,
    'sync_word': 0x12,
    'preamble_length': 8
}

spi = SPI(1, baudrate=100000, sck=Pin(18), mosi=Pin(23), miso=Pin(19))
lora = SX127x(spi, lora_pins, lora_params)

print("LoRa Receiver Listening...")

while True:
    # ฟังก์ชัน receive จะคืนค่า (payload, rssi) ถ้าได้รับข้อมูล
    payload, rssi = lora.receive()
    
    if payload:
        print("Received:", payload)
        print("RSSI:", rssi)
    
    time.sleep(0.1) # หน่วงเวลานิดหน่อย