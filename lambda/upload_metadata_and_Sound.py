import json
import boto3
import os
from decimal import Decimal 
from urllib.parse import unquote_plus
from datetime import datetime

s3 = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')

# Environment Variables
AUDIO_BUCKET = os.environ.get('AUDIO_BUCKET')
METADATA_BUCKET = os.environ.get('METADATA_BUCKET')
ABNORMAL_BUCKET = os.environ.get('ABNORMAL_BUCKET')
TABLE_NAME = os.environ.get('TABLE_NAME')

def lambda_handler(event, context):
    table = dynamodb.Table(TABLE_NAME)
    
    for record in event['Records']:
        source_bucket = record['s3']['bucket']['name']
        source_key = unquote_plus(record['s3']['object']['key'])
        
        filename = os.path.basename(source_key) # เช่น 20250719_0633_ESP32...wav
        extension = filename.lower().split('.')[-1]
        target_bucket = ""

        # --- 1. Logic สร้าง Subfolder จากชื่อไฟล์ ---
        try:
            # สมมติชื่อไฟล์: 20250719_0633_...
            # แยกด้วย underscore (_) แล้วเอาตัวแรก -> "20250719"
            date_part = filename.split('_')[0] 
            
            if len(date_part) == 8 and date_part.isdigit():
                year = date_part[0:4]   # "2025"
                month = date_part[4:6]  # "07"
                day = date_part[6:8]    # "19"
                folder_prefix = f"{year}/{month}/{day}"
            else:
                raise ValueError("Date format mismatch")
                
        except Exception as e:
            # กรณีชื่อไฟล์ไม่ตรงรูปแบบ (เช่น test.wav) ให้ใช้วันที่ปัจจุบันแทน
            print(f"⚠️ Cannot parse date from filename: {e}. Using Today's date.")
            now = datetime.now()
            folder_prefix = now.strftime('%Y/%m/%d')
        
        # สร้าง Key ปลายทาง: "2025/07/19/ชื่อไฟล์เดิม"
        target_key = f"{folder_prefix}/{filename}"
        # -------------------------------------------

        # 2. จัดการ JSON
        if extension == 'json':
            target_bucket = METADATA_BUCKET
            try:
                response = s3.get_object(Bucket=source_bucket, Key=source_key)
                data = json.loads(response['Body'].read().decode('utf-8'), parse_float=Decimal)
                
                table.put_item(
                    Item={
                        'DATE': data.get('timestamp'),          
                        'DEVICE': data.get('board_id'),         
                        'species': [],                          
                        'temperature_c': data.get('temperature_c'),
                        'humidity': data.get('humidity_percent'),
                        'light': data.get('light_adc'),
                        'location': data.get('location'),       
                        'status': 'pending_analysis',
                        's3_path': target_key  # บันทึก Path ใหม่เก็บไว้
                    }
                )
                print(f"✅ Data for {data.get('board_id')} saved to DynamoDB")
            except Exception as e:
                print(f"⚠️ DynamoDB Save Error: {e}")

        # 3. จัดการ WAV
        elif extension == 'wav':
            target_bucket = AUDIO_BUCKET
            print(f"🎵 Audio file detected: {filename}")

        # 4. ไฟล์อื่นๆ
        else:
            target_bucket = ABNORMAL_BUCKET
            print(f"⚠️ Unknown file type. Moving to Quarantine.")

        # ขั้นตอนการย้ายไฟล์
        if target_bucket:
            try:
                copy_source = {'Bucket': source_bucket, 'Key': source_key}
                
                s3.copy_object(CopySource=copy_source, Bucket=target_bucket, Key=target_key)
                s3.delete_object(Bucket=source_bucket, Key=source_key)
                
                print(f"🚀 Moved to: {target_bucket}/{target_key}")
            except Exception as e:
                print(f"❌ Move failed: {e}")

    return {'statusCode': 200}