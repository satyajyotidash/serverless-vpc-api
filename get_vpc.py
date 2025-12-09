import os
import json
import boto3
from botocore.exceptions import ClientError

dynamodb = boto3.resource('dynamodb')
TABLE = os.environ.get('TABLE_NAME', 'VpcRecords')
table = dynamodb.Table(TABLE)

def handler(event, context):
    """
    GET handler:
    - If query param vpcId provided returns single item
    - Otherwise returns all items (scan) - acceptable for demo
    """
    params = event.get('queryStringParameters') or {}
    vpc_id = params.get('vpcId') if params else None

    try:
        if vpc_id:
            resp = table.get_item(Key={'vpcId': vpc_id})
            item = resp.get('Item')
            if not item:
                return {'statusCode': 404, 'body': json.dumps({'message':'Not found'})}
            return {'statusCode': 200, 'body': json.dumps(item)}
        else:
            resp = table.scan()
            items = resp.get('Items', [])
            return {'statusCode': 200, 'body': json.dumps({'vpcs': items})}
    except ClientError as e:
        return {'statusCode': 500, 'body': json.dumps({'error': str(e)})}
