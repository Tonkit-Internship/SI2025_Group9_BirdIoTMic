import network
import time
import ntptime
from machine import Pin, I2C
import utime
from ds3231 import DS3231   # ใช้ไฟล์ ds3231.py ที่คุณมี

# ====== กำหนด WiFi ======
WIFI_SSID = "Meen8888"
WIFI_PASS = "08032548"

def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(WIFI_SSID, WIFI_PASS)
    print("กำลังเชื่อมต่อ WiFi...")
    
    retry = 0
    while not wlan.isconnected() and retry < 20:
        print(".", end="")
        time.sleep(0.5)
        retry += 1
    
    if wlan.isconnected():
        print("\nเชื่อมต่อสำเร็จ:", wlan.ifconfig())
        return True
    else:
        print("\nเชื่อมต่อไม่สำเร็จ")
        return False

# ====== กำหนด I2C ของ DS3231 ======
i2ctime = I2C(0, scl=Pin(19), sda=Pin(18))
rtc = DS3231(i2ctime)

# ====== Sync เวลา ======
if connect_wifi():
    try:
        ntptime.settime()   # sync เวลา (UTC)
        print("ซิงค์เวลาสำเร็จ")

        # เวลาใน ESP32 (UTC) → ต้องบวก offset ไทย (+7 ชั่วโมง)
        TIME_OFFSET = 7 * 3600
        t = time.localtime(time.time() + TIME_OFFSET)

        # เตรียมข้อมูลให้ตรงกับ set_datetime(y, m, d, hh, mm, ss)
        year, month, mday, hour, minute, second, _, _ = t
        rtc.set_datetime((year, month, mday, hour, minute, second))

        print("ตั้งค่า RTC เรียบร้อย:", rtc.datetime())

    except Exception as e:
        print("ซิงค์เวลาไม่สำเร็จ:", e)
else:
    print("ใช้เวลาใน DS3231 ต่อไป:", rtc.datetime())

# ====== ตัวอย่าง: พิมพ์เวลาออกมาทุก 1 วินาที ======
while True:
    print("RTC:", rtc.datetime())
    utime.sleep(1)
