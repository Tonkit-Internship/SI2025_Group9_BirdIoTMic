import json
import boto3
from boto3.dynamodb.conditions import Key
import decimal
from operator import itemgetter

class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, decimal.Decimal):
            return float(o)
        return super().default(o)

def lambda_handler(event, context):
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('bird_iot_mic')

    # ดึง query string parameter จาก API Gateway
    params = event.get("queryStringParameters") or {}
    mode = params.get("mode", "all")
    device_id = params.get("device_id", None)

    items = []

    if mode == "device" and device_id:
        # ถ้ามี Sort Key ด้วย → ใช้ query() ดีกว่า
        response = table.scan(
            FilterExpression=Key("DEVICE").eq(device_id)
        )
        items = response.get("Items", [])
        items = sorted(items, key=itemgetter("DATE"), reverse=True)

    elif mode == "latest":
        response = table.scan()
        items = response.get("Items", [])
        # เรียงตาม DATE จากใหม่สุดไปเก่าสุด
        items = sorted(items, key=itemgetter("DATE"), reverse=True)

    else:
        # ดึงทั้งหมด ไม่เรียง
        response = table.scan()
        items = response.get("Items", [])

    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*"
        },
        "body": json.dumps(items, cls=DecimalEncoder)
    }
