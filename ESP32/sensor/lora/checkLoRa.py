from machine import Pin, SPI
import time

# ตั้งค่าขา (ตามที่คุณใช้)
SCK = 18
MISO = 19
MOSI = 23
SS = 5

spi = SPI(1, baudrate=100000, sck=Pin(SCK), mosi=Pin(MOSI), miso=Pin(MISO))
ss = Pin(SS, Pin.OUT)
ss.value(1)

# อ่านค่า Register 0x42 (Version Register)
ss.value(0)
spi.write(bytes([0x42 & 0x7F])) # สั่งอ่านที่อยู่ 0x42
ver = spi.read(1)[0]
ss.value(1)

print("LoRa Chip Version: ", hex(ver))

"""
ถ้าขึ้น 0x12 หรือ 0x22 = ต่อสายถูกแล้ว 
ถ้าขึ้น 0x0 หรือ 0xff = ต่อสายผิด/หลวม หรือโมดูลเสีย 
"""