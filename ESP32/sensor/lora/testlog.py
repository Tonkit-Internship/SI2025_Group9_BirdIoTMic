from machine import Pin, SPI, RTC
from sx127x import SX127x
import time

# --- 1. ตั้งค่า LoRa ---
lora_pins = { 'ss': Pin(5, Pin.OUT), 'rst': Pin(25, Pin.OUT), 'dio0': Pin(26, Pin.IN) }
lora_params = {
    'frequency': 433000000,
    'bandwidth': 125000,
    'sf': 7,
    'cr': 5,
    'sync_word': 0x12,
    'preamble_length': 8
}
# ใช้ความเร็ว 100k เพื่อความเสถียร
spi = SPI(1, baudrate=100000, sck=Pin(18), mosi=Pin(23), miso=Pin(19))
lora = SX127x(spi, lora_pins, lora_params)

# --- 2. ตั้งค่าเวลาจำลอง (RTC) ---
rtc = RTC()
# Set time: 2025-07-29 16:49:34
rtc.datetime((2025, 7, 29, 2, 16, 49, 34, 0)) 

# --- 3. ฟังก์ชันส่ง Log ---
def send_log(message):
    t = rtc.datetime()
    # Format: [YYYY-MM-DD HH:MM:SS]
    timestamp = "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(t[0], t[1], t[2], t[4], t[5], t[6])
    
    full_log = "[{}] {}".format(timestamp, message)
    
    print("Sending:", full_log) 
    lora.send(full_log)        
    time.sleep(0.5) # หน่วงเวลาเล็กน้อยกัน Buffer เต็ม

# --- 4. เริ่มจำลองการทำงาน ---
print("System Ready...")
time.sleep(2)

# เริ่มจับเวลา
start_time = time.time()

send_log("Start recording audio...")

time.sleep(2) 
send_log("Metadata saved -> 20250729_file.json")

time.sleep(2)
send_log("Recording finished -> 20250729_file.wav")

time.sleep(1)
send_log("[OK] Upload success: /sd/data/file.wav")
send_log("File moved -> file.wav")

time.sleep(1)
send_log("[OK] Upload success: /sd/data/file.json")
send_log("No more files to upload.")

# จบการทำงาน
end_time = time.time()
duration = end_time - start_time

send_log("[OK] Timestamp: {}".format(rtc.datetime()))
send_log("Process finished. Duration: {:.2f} sec".format(duration))
send_log("SD Card unmounted.")