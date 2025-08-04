import json
import os
import boto3
from datetime import datetime
from decimal import Decimal  # <-- เพิ่ม

s3_client = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('bird_iot_mic')

BUCKET_NAME = os.environ.get('BUCKET_NAME', 'bird.iot.mic')

def lambda_handler(event, context):
    print("EVENT:", json.dumps(event))
    try:
        if "body" in event:
            body = json.loads(event['body'])
        else:
            body = event
        
        device_id = body['device_id']
        data = body['data']

        presigned_urls_all = {}

        for entry in data:
            timestamp = entry['timestamp']
            files = entry.get('files', [])
            location = entry.get('location', 'unknown')
            
            # แปลง float เป็น Decimal
            temperature = entry.get('temperature_c', None)
            if temperature is not None:
                temperature = Decimal(str(temperature))
            
            humidity = entry.get('humidity_percent', None)
            if humidity is not None:
                humidity = Decimal(str(humidity))

            dt = datetime.fromisoformat(timestamp.replace("Z", ""))
            date_str = dt.strftime("%Y-%m-%d")
            hour_str = dt.strftime("%H")
            device_id =  entry['board_id']
            light_adc  = entry['light_adc']
            presigned_urls = {}
            for filename in files:
                key = f"{date_str}/{device_id}/{hour_str}/{filename}"
                url = s3_client.generate_presigned_url(
                    'put_object',
                    Params={'Bucket': BUCKET_NAME, 'Key': key, 'ContentType': 'audio/wav'},
                    ExpiresIn=300
                )
                presigned_urls[filename] = url

            presigned_urls_all[timestamp] = presigned_urls

            table.put_item(Item={
                "DATE": timestamp,   
                "DEVICE": device_id,
                "location": location,
                "temperature_c": temperature,
                "humidity": humidity,
                "light" : light_adc,
                "files": files,
                "species": []
            })

        return {
            'statusCode': 200,
            'body': json.dumps({'presigned_urls': presigned_urls_all}),
            'headers': {'Content-Type': 'application/json'}
        }

    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)}),
            'headers': {'Content-Type': 'application/json'}
        }
