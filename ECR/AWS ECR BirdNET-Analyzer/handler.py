import os
import sys
import subprocess
import boto3
import subprocess
from numba.core import config
import csv
config.DISABLE_JIT = True
from urllib.parse import unquote

os.environ["NUMBA_DISABLE_JIT"] = "1"

from boto3.dynamodb.conditions import Key
from datetime import datetime

def update_species_in_dynamodb(csv_file_path, file_name):
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('bird_iot_mic')

    parts = file_name.split("_")
    if len(parts) < 3:
        print("❌ Invalid file name format")
        return

    date_key = f"{parts[0]}_{parts[1]}"  # ex: 20250719_0540
    device_id = parts[2]                # ex: ESP32-02

    # ดึง species จาก csv
    species_new = set()
    print(species_new)
    try:
        with open(csv_file_path, newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                try:
                    if float(row['Confidence']) > 0.6 :
                        if row['Common name'] and row['Common name'] != "-":
                            print(row['Common name'])
                            species_new.add(row['Common name'])
                            print(species_new)
                except:
                    continue
    except Exception as e:
        print(f"❌ Error reading CSV: {e}")
        return

    if not species_new:
        print("⚠️ No high-confidence species detected → setting species = []")
        try:
            table.update_item(
                Key={'DATE': date_key, 'DEVICE': device_id},
                UpdateExpression='SET species = :val',
                ExpressionAttributeValues={':val': []}
            )
        except Exception as e:
            print(f"❌ Error clearing species: {e}")
        return
    try:
        # อ่านข้อมูลปัจจุบัน
        response = table.get_item(Key={'DATE': date_key, 'DEVICE': device_id})
        item = response.get('Item', {})
        existing_species = set(item.get('species', []))

        updated_species = sorted(species_new)


        # อัปเดตเฉพาะฟิลด์ species
        table.update_item(
            Key={'DATE': date_key, 'DEVICE': device_id},
            UpdateExpression='SET species = :val',
            ExpressionAttributeValues={':val': updated_species}
        )

        print(f"✅ Updated species for {date_key} {device_id}: {updated_species}")

    except Exception as e:
        print(f"❌ Error updating DynamoDB: {e}")



def is_audio_file(filename):
    audio_extensions = ('.mp3', '.wav', '.flac', '.m4a', '.ogg', '.aac')
    return filename.lower().endswith(audio_extensions)

def lambda_handler(event, context):
    s3 = boto3.client('s3')

    bucket = event['Records'][0]['s3']['bucket']['name']
    key = unquote(event['Records'][0]['s3']['object']['key'])


    print(f"Received event for bucket: {bucket}, key: {key}")
    if not is_audio_file(key):
        print(f"File {key} is not an audio file. Skipping processing.")
        return {
            "statusCode": 200,
            "message": "Not an audio file, skipping."
        }
    

    safe_key = key.replace(' ', '_')
    folder_path = os.path.dirname(safe_key)
    base_name = os.path.basename(safe_key).rsplit('.', 1)[0]
    input_file = f'/tmp/{base_name}'
    
    output_dir = '/tmp/output'
    os.makedirs(output_dir, exist_ok=True)

    print(f"Downloading s3://{bucket}/{key} to {input_file}")

    try:
        s3.download_file(bucket, key, input_file)
        print("Download completed")
    except Exception as e:
        print(f"Error downloading file: {e}")
        raise

    print("Starting BirdNET analysis...")
    
    env = os.environ.copy()
    env["NUMBA_CACHE_DIR"] = "/tmp"

    result = subprocess.run([
        sys.executable, "-m", "birdnet_analyzer.analyze",
        input_file,
        "--output", output_dir,
        "--lat", "13.75",
        "--lon", "100.50",
        "--rtype", "csv",
        "--locale", "en"
    ], capture_output=True, text=True, env={"NUMBA_CACHE_DIR": "/tmp"})

    print(f"BirdNET return code: {result.returncode}")
    print(f"BirdNET stdout: {result.stdout}")
    print(f"BirdNET stderr: {result.stderr}")

    # หาชื่อไฟล์ .csv ที่เป็นผลลัพธ์
    csv_files = [f for f in os.listdir(output_dir) if f.endswith(".csv") and "results" in f]

    if csv_files:
        output_file = os.path.join(output_dir, csv_files[0])
        output_key = safe_key.rsplit('.', 1)[0] + "_output.csv"
        print(f"Uploading result file {output_file} to s3://{bucket}/{output_key}")
        try:
            s3.upload_file(output_file, bucket, output_key)
            print("Upload completed")
            update_species_in_dynamodb(output_file, base_name)
        except Exception as e:
            print(f"Error uploading file: {e}")
            raise
    else:
        print("No CSV file found in output directory.")
        print("Files in output directory:", os.listdir(output_dir))

        error_log_path = "/tmp/error_log.txt"
        if os.path.exists(error_log_path):
            with open(error_log_path, "r") as elog:
                error_log_content = elog.read()
            print("==== ERROR LOG CONTENT ====")
            print(error_log_content)
        else:
            print("No error log found.")

        return {
            "statusCode": 500,
            "error": "CSV output file not found",
            "stdout": result.stdout,
            "stderr": result.stderr
        }
    try:
        if os.path.exists(input_file):
            os.remove(input_file)
        if os.path.exists(output_dir):
            for f in os.listdir(output_dir):
                os.remove(os.path.join(output_dir, f))
            os.rmdir(output_dir)  
        print("✅ Cleanup completed")
    except Exception as cleanup_error:
        print(f"⚠️ Cleanup failed: {cleanup_error}")

    return {
        "statusCode": 200,
        "stdout": result.stdout,
        "stderr": result.stderr
    }