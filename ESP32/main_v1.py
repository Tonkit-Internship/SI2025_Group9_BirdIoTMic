# =======================
# 🔹 IMPORT LIBRARIES
# =======================
from machine import Pin, I2C, ADC, I2S, SDCard
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
from config import WIFI_SSID, WIFI_PASS, BOARD_ID, LOCATION, API_URL
"""
from shtc3 import SHTC3
"""

# =======================
# 🔹 CONFIGURATION
# =======================
USE_MOCK = False  # ตั้งค่า True,False เพื่อใช้ mock และอัปโหลดจริง
POWER_CONTROL_ADDR = 0x70
POWER_CONTROL_OFF = 0x81
RECORD_TIME = 60
SAMPLING_RATE = 44100
RECORD_SIZE = SAMPLING_RATE * RECORD_TIME * 2

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
    t = time.localtime(time.time() + time_offset)
    return t, "{:04d}{:02d}{:02d}_{:02d}{:02d}".format(*t[:5])

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
def get_unuploaded_files():
    files = os.listdir("/sd/data")
    return [f for f in files if f.endswith(".wav")]

def upload_presigned_file(filepath, url):
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

            s.write(f"PUT {path} HTTP/1.1\r\nHost: {host}\r\nContent-Type: audio/wav\r\nContent-Length: {size}\r\nConnection: close\r\n\r\n".encode())

            while True:
                chunk = f.read(2048)
                if not chunk:
                    break
                s.write(chunk)

            s.close()
            log(f"✅ อัปโหลดสำเร็จ: {filepath}")

    except Exception as e:
        log(f"❌ อัปโหลดล้มเหลว: {filepath} → {e}")


def mock_presigned_urls(metadata):
    result = {}
    for entry in metadata["data"]:
        ts = entry["timestamp"]
        result[ts] = {}
        for fname in entry["files"]:
            result[ts][fname] = f"https://mock.aws.fake-bucket/{fname}"
    return result

def upload_all_to_aws():
    pending = get_unuploaded_files()
    if not pending:
        log("ไม่มีไฟล์ที่ต้องอัปโหลด")
        return

    for wav in pending:
        base = wav.rsplit(".", 1)[0]
        js = base + ".json"

        # --- Load JSON ---
        try:
            with open(f"/sd/data/{js}") as f:
                meta = ujson.load(f)
        except Exception as e:
            log(f"ไม่พบหรืออ่าน JSON ไม่ได้: {js} → {e}")
            continue

        meta["files"] = [wav, js]
        metadata = {"device_id": BOARD_ID, "data": [meta]}  # 👈 ส่งแค่ชุดเดียว

        # --- ขอ presigned URL สำหรับชุดนี้เท่านั้น ---
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

        # --- อัปโหลดทีละไฟล์ในชุดนั้น ---
        ts = meta["timestamp"]
        for fname in meta["files"]:
            path = f"/sd/data/{fname}"
            url = presigned.get(ts, {}).get(fname, "")
            if url:
                upload_presigned_file(path, url)
                os.rename(path, f"/sd/uploaded/{fname}")
                log(f"อัปโหลดและย้ายไฟล์แล้ว → {fname}")
            else:
                log(f"ไม่มี URL สำหรับไฟล์นี้: {fname}")
        gc.collect()



# =======================
# 🔹 MAIN PROGRAM START
# =======================

# -- Set Time --

try:
    connect_wifi()
    ntptime.settime()
    time_offset = 7 * 3600
    print("ตั้งเวลาเรียบร้อย")
except:
    time_offset = 7 * 3600
    print("ตั้งเวลาไม่สำเร็จ ใช้เวลาท้องถิ่น")

# -- Mount SD --
sdcard = SDCard(slot=1)
os.mount(sdcard, "/sd")

for folder in ["data", "uploaded"]:
    if folder not in os.listdir("/sd"):
        os.mkdir(f"/sd/{folder}")

log_path = "/sd/log.txt"
if "log.txt" not in os.listdir("/sd"):
    with open(log_path, "w") as f:
        f.write("=== เริ่มบันทึก Log ===\n")

log("Mount SD card สำเร็จ")

# -- Setup Microphone --
sck = Pin(26)
ws = Pin(25)
sd = Pin(33)
mic = I2S(
    0, sck=sck, ws=ws, sd=sd,
    mode=I2S.RX, bits=16, format=I2S.MONO,
    rate=SAMPLING_RATE, ibuf=8192
)

# -- Record Audio --
t, timestamp = get_thai_time()
base = f"{timestamp}_{BOARD_ID}_{LOCATION}"
json_path = f"/sd/data/{base}.json"
wav_path = f"/sd/data/{base}.wav"
log("เริ่มบันทึกเสียง...")

"""
# SENSOR
temp, hum = sensor.measure()
light = light_sensor.read()
"""
meta = {
    "timestamp": timestamp,
    "board_id": BOARD_ID,
    "location": LOCATION,
    "temperature_c": 00,
    "humidity_percent": 00,
    "light_adc": 00
}
with open(json_path, "w") as f:
    json.dump(meta, f)
log(f"บันทึก metadata แล้ว → {base}.json")


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

# -- Upload --
i2c = I2C(1, sda=Pin(21), scl=Pin(22))
upload_all_to_aws()

# -- Unmount and Sleep --
log("ยกเลิกเชื่อมต่อ SD แล้ว")
os.umount("/sd")
power_off_for(i2c, 1800)


