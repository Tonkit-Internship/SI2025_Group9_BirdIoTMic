# =======================
# 🔹 IMPORT LIBRARIES
# =======================
from machine import Pin, I2C, ADC, I2S, SDCard, RTC, UART
import time
import os
import json
import ntptime
import network
import urequests
import ujson
import usocket
import ssl
import gc
from config import WIFI_SSID, WIFI_PASS, BOARD_ID, API_URL
from shtc3 import SHTC3
from ds3231 import DS3231

# =======================
# 🔹 CONFIGURATION
# =======================
USE_MOCK = False  
POWER_CONTROL_ADDR = 0x70
POWER_CONTROL_OFF = 0x81
RECORD_TIME = 60
SAMPLING_RATE = 44100
RECORD_SIZE = SAMPLING_RATE * RECORD_TIME * 2
rtc_esp  = RTC()


# =======================
# 🔹 FUNCTION DEFINITIONS
# =======================

# ---- Power Control ----
def power_off_for(i2c, seconds):
    high = seconds // 256
    low = seconds % 256
    i2c.writeto(
        POWER_CONTROL_ADDR,
        bytearray([POWER_CONTROL_OFF, low, high])
    )

# ---- WiFi ----
def connect_wifi(timeout=10):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        print("เชื่อมต่อ WiFi...")
        wlan.connect(WIFI_SSID, WIFI_PASS)

        start = time.time()
        while not wlan.isconnected():
            if time.time() - start > timeout:
                print("เชื่อมต่อ WiFi ไม่สำเร็จภายในเวลา")
                break
            time.sleep(0.3)

    if wlan.isconnected():
        print("WiFi IP:", wlan.ifconfig()[0])
    else:
        print("ไม่ได้เชื่อม WiFi")

def wifi_connected():
    sta_if = network.WLAN(network.STA_IF)
    return sta_if.isconnected()

# แปลง NMEA เป็น Decimal Degrees
def nmea_to_decimal(coord, direction):
    deg = int(coord / 100)
    minutes = coord - deg * 100
    dd = deg + minutes / 60
    if direction in ['S', 'W']:
        dd = -dd
    return dd

# อ่าน GGA sentence แล้วคืนค่า lat/lon
def parse_gga(sentence):
    parts = sentence.split(',')
    try:
        fix = int(parts[6])
        if fix == 0:
            return None, None  # ยังไม่ได้ fix
        lat = nmea_to_decimal(float(parts[2]), parts[3])
        lon = nmea_to_decimal(float(parts[4]), parts[5])
        return lat, lon
    except:
        return None, None
    
# ---- Logging ----
def log(text, log_path="/sd/log.txt"):
    try:
        timestamp = time.localtime(time.time() + time_offset)
        timestr = "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(*timestamp[:6])
        message = f"[{timestr}] {text}\n"
        print(message.strip())
        with open(log_path, "a") as f:
            f.write(message)
    except Exception as e:
        print("ไม่สามารถเขียน log ได้:", e)

# ---- Time ----
def get_thai_time():
    y, m, d, hh, mm, ss = rtc_ds.datetime()
    timestr = "{:04d}{:02d}{:02d}_{:02d}{:02d}".format(y, m, d, hh, mm)
    return (y, m, d, hh, mm, ss), timestr

# ---- Time Sleep ----
def get_record_interval():
    # ดึงเวลาปัจจุบันจาก RTC หรือ time.localtime()
    now = time.localtime()
    hour = now[3]
    minute = now[4]
    if (5 <= hour < 8) or (hour == 8 and minute == 0):
        return 5 * 60   
    if (17 <= hour < 18) or (hour == 18 and minute <= 30):
        return 5 * 60   
    return 30 * 60  

# ---- Audio WAV Header ----
def create_wav_header(sr, bps, ch, n):
    dsize = n * ch * bps // 8
    return (
        b"RIFF" + (dsize + 36).to_bytes(4, "little") + b"WAVEfmt " +
        (16).to_bytes(4, "little") + (1).to_bytes(2, "little") +
        (ch).to_bytes(2, "little") + (sr).to_bytes(4, "little") +
        (sr * ch * bps // 8).to_bytes(4, "little") +
        (ch * bps // 8).to_bytes(2, "little") + (bps).to_bytes(2, "little") +
        b"data" + dsize.to_bytes(4, "little")
    )

# ---- Upload to AWS ----
def get_unuploaded_files(batch_size=5, ):
    files = os.listdir("/sd/data")
    wav_files = [f for f in files if f.endswith(".wav")]
    return wav_files[0:batch_size]

def upload_presigned_file(filepath, url):
    #check ram
    free_ram = gc.mem_free()
    gc.collect()
    print("RAM upload_presigned_file เหลืออยู่ (bytes):", free_ram)
    if USE_MOCK:
        log(f"(mock) อัปโหลด: {filepath} → {url}")
        time.sleep(0.5)
        return

    try:
        _, _, host_path = url.partition("https://")
        host, _, path = host_path.partition("/")
        path = "/" + path

        with open(filepath, "rb") as f:
            size = os.stat(filepath)[6]
            addr = usocket.getaddrinfo(host, 443)[0][-1]
            s = usocket.socket()
            s.connect(addr)
            s = ssl.wrap_socket(s, server_hostname=host)
            gc.collect()
            s.write(f"PUT {path} HTTP/1.1\r\nHost: {host}\r\nContent-Type: audio/wav\r\nContent-Length: {size}\r\nConnection: close\r\n\r\n".encode())

            while True:
                chunk = f.read(2000)
                if not chunk:
                    break
                s.write(chunk)
                gc.collect()
            s.close()
            log(f"✅ อัปโหลดสำเร็จ: {filepath}")

    except Exception as e:
        log(f"❌ อัปโหลดล้มเหลว: {filepath} → {e}")
        
    gc.collect()


def mock_presigned_urls(metadata):
    result = {}
    for entry in metadata["data"]:
        ts = entry["timestamp"]
        result[ts] = {}
        for fname in entry["files"]:
            result[ts][fname] = f"https://mock.aws.fake-bucket/{fname}"
    return result

def upload_all_to_aws(batch_size=3):
    offset = 0
    while True:
        pending = get_unuploaded_files(batch_size=batch_size)
        if not pending:
            log("ไม่มีไฟล์ที่ต้องอัปโหลดเพิ่มแล้ว")
            break
        
        for wav in pending:
            elapsed = time.time() - start_time  
            if elapsed >= 360:
                log("⏹ เหลือเวลาไม่พอสำหรับอัปโหลดไฟล์ถัดไป ปิดเครื่องเลย")
                return
            base = wav.rsplit(".", 1)[0]
            js = base + ".json"

            try:
                with open(f"/sd/data/{js}") as f:
                    meta = ujson.load(f)
            except Exception as e:
                log(f"ไม่พบหรืออ่าน JSON ไม่ได้: {js} → {e}")
                continue

            meta["files"] = [wav, js]
            metadata = {"device_id": BOARD_ID, "data": [meta]}
            
            free_ram = gc.mem_free()
            print("RAM upload_all_to_awsใน for เหลืออยู่ (bytes):", free_ram)
            gc.collect()

            if USE_MOCK:
                presigned = mock_presigned_urls(metadata)
            else:
                try:
                    resp = urequests.post(API_URL, data=ujson.dumps(metadata), headers={"Content-Type": "application/json"})
                    presigned = ujson.loads(resp.text)["presigned_urls"]
                    resp.close()
                except Exception as e:
                    log(f"❌ อัปโหลด metadata ไม่ได้: {e}")
                    continue

            gc.collect()

            ts = meta["timestamp"]
            for fname in meta["files"]:
                path = f"/sd/data/{fname}"
                url = presigned.get(ts, {}).get(fname, "")
                if url:
                    upload_presigned_file(path, url)
                    gc.collect()
                    os.rename(path, f"/sd/uploaded/{fname}")
                    log(f"อัปโหลดและย้ายไฟล์แล้ว → {fname}")
                else:
                    log(f"ไม่มี URL สำหรับไฟล์นี้: {fname}")
                gc.collect()



# =======================
# 🔹 MAIN PROGRAM START
# =======================
# -- Mount SD --
sdcard = SDCard(slot=1)
os.mount(sdcard, "/sd")

#check ram
free_ram = gc.mem_free()
print("RAM เหลืออยู่ (bytes):", free_ram)
gc.collect()
i2ctime = I2C(0, scl=Pin(19), sda=Pin(18))
rtc_ds = DS3231(i2ctime)
# -- Set Time --
try:
    connect_wifi()
    ntptime.settime()
    time_offset = 7 * 3600
    print("ตั้งเวลาเรียบร้อย")
except:
    y, m, d, hh, mm, ss = rtc_ds.datetime()
    weekday = time.localtime(time.mktime((y, m, d, 0, 0, 0, 0, 0)))[6]
    rtc_esp.datetime((y, m, d, weekday, hh, mm, ss, 0))
    time_offset = 0
    print("ตั้งเวลาไม่สำเร็จ ใช้เวลา RTC")
start_time = time.time()



#check ram
free_ram = gc.mem_free()
print("RAM เหลืออยู่ (bytes):", free_ram)
gc.collect()

for folder in ["data", "uploaded"]:
    if folder not in os.listdir("/sd"):
        os.mkdir(f"/sd/{folder}")

log_path = "/sd/log.txt"
if "log.txt" not in os.listdir("/sd"):
    with open(log_path, "w") as f:
        f.write("=== เริ่มบันทึก Log ===\n")



# -- Setup Microphone --
sck = Pin(26)
ws = Pin(25)
sd = Pin(33)
mic = I2S(
    0, sck=sck, ws=ws, sd=sd,
    mode=I2S.RX, bits=16, format=I2S.MONO,
    rate=SAMPLING_RATE, ibuf=8192
)

# SENSOR
t, timestamp = get_thai_time()
i2cTemp = I2C(0, scl=Pin(17), sda=Pin(5), freq=100000)
sensor = SHTC3(i2cTemp)
light_sensor = ADC(Pin(32))
gps = UART(2, baudrate=9600, tx=13, rx=12)


temp, hum = sensor.measure()
light = light_sensor.read()
print("เริ่มรอ GPS fix...")
while True:
    if gps.any():
        line = gps.readline()
        if line:
            try:
                line_str = line.decode('utf-8').strip()
            except:
                continue
            if line_str.startswith('$GPGGA'):
                lat, lon = parse_gga(line_str)
                if lat is not None and lon is not None:
                    print("GPS fix ได้แล้ว!")
                    print(f"Latitude: {lat:.12f}")
                    print(f"Longitude: {lon:.12f}")
                    break  # ออก loop
    time.sleep(0.1)

i2ctime = I2C(0, scl=Pin(19), sda=Pin(18))
rtc_ds = DS3231(i2ctime)
t, timestamp = get_thai_time()
meta = {
    "timestamp": timestamp,
    "board_id": BOARD_ID,
    "location": f"{lat:.12f}, {lon:.12f}",
    "temperature_c": temp,
    "humidity_percent": hum,
    "light_adc": light
}

base = f"{timestamp}_{BOARD_ID}_{lat:.12f},{lon:.12f}"
json_path = f"/sd/data/{base}.json"
wav_path = f"/sd/data/{base}.wav"
with open(json_path, "w") as f:
    json.dump(meta, f)
log(f"บันทึก metadata แล้ว → {base}.json")

# -- Record Audio --
log("เริ่มบันทึกเสียง...")

#check ram
free_ram = gc.mem_free()
print("RAM เหลืออยู่ (bytes):", free_ram)
gc.collect()

mic_buffer = bytearray(2048)
mic_mv = memoryview(mic_buffer)
total = 0
with open(wav_path, "wb") as wav:
    wav.write(create_wav_header(SAMPLING_RATE, 16, 1, SAMPLING_RATE * RECORD_TIME))
    while total < RECORD_SIZE:
        n = mic.readinto(mic_mv)
        if n > 0:
            to_write = min(n, RECORD_SIZE - total)
            wav.write(mic_mv[:to_write])	
            total += to_write

log(f"บันทึกเสียงเสร็จแล้ว → {base}.wav")

#check ram
free_ram = gc.mem_free()
print("RAM เหลืออยู่ (bytes):", free_ram)
gc.collect()

# -- Upload --
if wifi_connected():
    upload_all_to_aws()


elapsed = time.time() - start_time
log(f"โค้ดทำงานเสร็จ ใช้เวลา {elapsed:.2f} วินาที")

# -- Unmount and Sleep --
log("ยกเลิกเชื่อมต่อ SD แล้ว")
os.umount("/sd")
timesleep = get_record_interval()-int(elapsed)-10
print("หลับ",timesleep)
i2c = I2C(1, sda=Pin(21), scl=Pin(22))
power_off_for(i2c, (timesleep))



