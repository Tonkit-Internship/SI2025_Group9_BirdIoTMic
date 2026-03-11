import os
import sys
import subprocess
import boto3
import shutil
import csv
import numpy as np
import soundfile as sf
import uuid
from urllib.parse import unquote

# ตั้งค่า Environment เพื่อความเสถียรบน AWS Lambda
os.environ["NUMBA_CACHE_DIR"] = "/tmp"
os.environ["MPLCONFIGDIR"] = "/tmp"
os.environ["KAGGLEHUB_CACHE"] = "/tmp"
os.environ["LD_LIBRARY_PATH"] = "/usr/lib64:" + os.environ.get("LD_LIBRARY_PATH", "")

def lambda_handler(event, context):
    s3 = boto3.client('s3')
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('data-birdiotmic')

    # 1. ดึงข้อมูลจาก S3 event
    bucket = event['Records'][0]['s3']['bucket']['name']
    key = unquote(event['Records'][0]['s3']['object']['key'])
    
    base_name = os.path.basename(key).rsplit('.', 1)[0]
    parts = base_name.split("_")
    
    if len(parts) >= 3:
        date_key = f"{parts[0]}_{parts[1]}" 
        device_id = parts[2]
        try:
            coords = parts[3].split(",")
            lat, lon = coords[0], coords[1]
        except:
            lat, lon = "13.75", "100.50"
    else:
        date_key = "unknown"
        device_id = "unknown"
        lat, lon = "13.75", "100.50"
    
    print(f"🚀 Processing Key: {key}")

    # 2. กำหนด Path สำหรับทำงาน (ใช้ UUID เพื่อป้องกันการชนกันของไฟล์)
    run_id = str(uuid.uuid4())[:8]
    work_dir = f"/tmp/birdnet_app_{run_id}"
    output_dir = f"/tmp/output_{run_id}"
    input_file = f'/tmp/input_{run_id}.wav'
    
    final_species = []

    try:
        # 3. เตรียมพื้นที่ทำงาน
        if os.path.exists(work_dir): shutil.rmtree(work_dir, ignore_errors=True)
        os.makedirs(output_dir, exist_ok=True)

        # 4. ก๊อปปี้ BirdNET และดาวน์โหลดไฟล์เสียง
        print("📦 Setting up BirdNET analyzer...")
        shutil.copytree("/var/task/birdnet_analyzer", f"{work_dir}/birdnet_analyzer")
        
        print(f"📥 Downloading audio to {input_file}")
        s3.download_file(bucket, key, input_file)

        # 5. รัน BirdNET Analysis
        env = os.environ.copy()
        env["PYTHONPATH"] = f"{work_dir}:" + env.get("PYTHONPATH", "")
        model_path = "/var/task/BirdNET_GLOBAL_6K_V2.4_Model"
        
        cmd = [
            sys.executable, "-m", "birdnet_analyzer.analyze",
            "-o", output_dir,
            "--lat", lat,
            "--lon", lon,
            "--rtype", "csv",
            "--min_conf", "0.1",
            "--sensitivity", "1.25",
            "--threads", "1",
            "-c", model_path,
            input_file
        ]

        print(f"📢 Executing BirdNET...")
        process = subprocess.Popen(
            cmd, cwd=work_dir, env=env, 
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
            text=True, bufsize=1
        )

        for line in iter(process.stdout.readline, ''):
            if line.strip(): print(f"[BirdNET]: {line.strip()}")
        
        process.stdout.close()
        process.wait()

        # 6. ประมวลผลผลลัพธ์
        result_files = [f for f in os.listdir(output_dir) if f.endswith('.csv') and "params" not in f]
        
        if result_files:
            csv_path = os.path.join(output_dir, result_files[0])
            
            # อัปโหลดผลวิเคราะห์กลับ S3
            history_key = f"analysis/history/{date_key}_{device_id}_result.csv"
            s3.upload_file(csv_path, 'analysis-birdiotmic', history_key)

            # อ่านรายชื่อนก
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                species_set = set()
                for row in reader:
                    conf = row.get('Confidence') or row.get('confidence') or row.get('Score', 0)
                    name = row.get('Common name') or row.get('Species')
                    if name and float(conf) > 0.5:
                        species_set.add(name)
                final_species = list(species_set)

        # 7. อัปเดต DynamoDB
        if device_id != "unknown":
            table.update_item(
                Key={'DATE': date_key, 'DEVICE': device_id},
                UpdateExpression="SET species = :s, #st = :c",
                ExpressionAttributeNames={'#st': 'status'},
                ExpressionAttributeValues={':s': final_species, ':c': "analysis_completed"}
            )

    except Exception as e:
        print(f"❌ FATAL ERROR: {str(e)}")
        raise e

    finally:
        # 🔥 ส่วน Cleanup: ลบทุกอย่างทิ้งไม่ว่าจะสำเร็จหรือไม่
        print("🧹 Cleaning up workspace...")
        try:
            if os.path.exists(work_dir): shutil.rmtree(work_dir, ignore_errors=True)
            if os.path.exists(output_dir): shutil.rmtree(output_dir, ignore_errors=True)
            if os.path.exists(input_file): os.remove(input_file)
            print("✨ Workspace is clean.")
        except Exception as cleanup_err:
            print(f"⚠️ Cleanup warning: {str(cleanup_err)}")

    return {"status": "success", "detected_count": len(final_species)}