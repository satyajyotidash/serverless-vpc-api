import os
import json
import uuid
import boto3
from datetime import datetime

ec2 = boto3.client('ec2')
dynamodb = boto3.resource('dynamodb')
TABLE = os.environ.get('TABLE_NAME', 'VpcRecords')
table = dynamodb.Table(TABLE)

def handler(event, context):
    """
    Simple create VPC Lambda:
    - Creates a VPC with a generated CIDR
    - Creates two public subnets
    - Attaches an Internet Gateway and a public route
    - Stores metadata in DynamoDB table (vpcId as key)
    """
    # generate a simple unique CIDR to reduce collisions during demo
    third_octet = uuid.uuid4().int % 250
    cidr = f"10.{third_octet}.0.0/16"

    # 1. create VPC
    vpc_resp = ec2.create_vpc(CidrBlock=cidr)
    vpc_id = vpc_resp['Vpc']['VpcId']

    # enable DNS
    ec2.modify_vpc_attribute(VpcId=vpc_id, EnableDnsSupport={'Value': True})
    ec2.modify_vpc_attribute(VpcId=vpc_id, EnableDnsHostnames={'Value': True})

    # 2. create Internet Gateway and attach
    igw = ec2.create_internet_gateway()['InternetGateway']['InternetGatewayId']
    ec2.attach_internet_gateway(InternetGatewayId=igw, VpcId=vpc_id)

    # 3. create route table and default route
    rt = ec2.create_route_table(VpcId=vpc_id)['RouteTable']['RouteTableId']
    ec2.create_route(RouteTableId=rt, DestinationCidrBlock='0.0.0.0/0', GatewayId=igw)

    # 4. determine AZs (use available AZs)
    azs = [az['ZoneName'] for az in ec2.describe_availability_zones()['AvailabilityZones']][:2]
    if not azs:
        azs = [None, None]

    # 5. create two public subnets and associate with route table
    public_subnets = []
    subnet_cidrs = [f"10.{third_octet}.1.0/24", f"10.{third_octet}.2.0/24"]
    for i, cidr_sub in enumerate(subnet_cidrs):
        az = azs[i % len(azs)]
        subnet = ec2.create_subnet(VpcId=vpc_id, CidrBlock=cidr_sub, AvailabilityZone=az)['Subnet']
        subnet_id = subnet['SubnetId']
        # auto-assign public IPs
        ec2.modify_subnet_attribute(SubnetId=subnet_id, MapPublicIpOnLaunch={'Value': True})
        ec2.associate_route_table(RouteTableId=rt, SubnetId=subnet_id)
        public_subnets.append({'SubnetId': subnet_id, 'Cidr': cidr_sub, 'Az': az})

    # 6. tag resources
    timestamp = datetime.utcnow().isoformat() + 'Z'
    tags = [{'Key':'Name','Value':f'demo-vpc-{third_octet}'},
            {'Key':'CreatedAt','Value':timestamp}]
    ec2.create_tags(Resources=[vpc_id, igw, rt] + [s['SubnetId'] for s in public_subnets], Tags=tags)

    # 7. persist metadata
    item = {
        'vpcId': vpc_id,
        'cidr': cidr,
        'publicSubnets': public_subnets,
        'internetGateway': igw,
        'routeTable': rt,
        'createdAt': timestamp
    }
    table.put_item(Item=item)

    return {
        'statusCode': 201,
        'body': json.dumps({'message':'VPC created', 'vpc': item})
    }
