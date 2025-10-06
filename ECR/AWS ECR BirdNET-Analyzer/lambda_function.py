import json
import os
from birdnet_analyzer.analyze import analyze

def lambda_handler(event, context):
    try:
        # จำลองไฟล์เสียงจาก event หรือโหลดมาจาก S3
        audio_file = "/tmp/input.wav"
        output_dir = "/tmp/output"
        os.makedirs(output_dir, exist_ok=True)

        # ตัวอย่าง: อาจโหลดไฟล์เสียงจาก S3 มาก่อน (ในอนาคต)
        # ตอนนี้ใช้ไฟล์ทดสอบใน image
        test_file = "test_clean.wav"  # ต้อง COPY ไปใน image ด้วย

        analyze(
            audio_input=test_file,
            output=output_dir,
            lat=13.75,
            lon=100.50,
            rtype="csv",
            locale="en"
        )

        # โหลดผลลัพธ์ที่ได้
        with open(f"{output_dir}/BirdNET_CombinedTable.csv", "r") as f:
            result = f.read()

        return {
            "statusCode": 200,
            "body": result
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "error": str(e)
        }
