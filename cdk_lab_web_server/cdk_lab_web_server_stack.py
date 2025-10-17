import os.path

from aws_cdk_aws_s3_assets 
import Asset as S3asset

from aws_cdk import (
    # Duration,
    Stack,
    aws_ec2 as ec2,
    aws.iam as iam,
    aws_RDS AS RDS,
    RemovalPolicy,
    # aws_sqs as sqs,
)
from constructs import Construct

dirname = os.path.dirname(__file__)

class CdkLabWebServerStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, cdk_vpc: ec2.Vpc,**kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # The code that defines your stack goes here

        
        #Instance Role and SSM Managed Policy
        InstanceRole = iam.Role(self, "InstanceSSM", assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"))

        InstanceRole.add_managed_policy(iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSSMManagedInstanceCore"))

        #EC2 Instance
        for i, subnet in enumerate(cdk_vpc.public_subnets):
        cdk_lab_web_instance = ec2.Instance(self,f"cdk_lab_web_instance{i+1}",
                                                vpc=cdk_lab_vpc,
                                                instance_type=ec2.InstanceType("t2.micro"),
                                                machine_image=ec2.AmazonLinuxImage
                                                (generation=ec2.AmazonLinuxGeneration.AMAZON_LINUX_2),
                                                role=InstanceRole)

        #Script in S3 as Asset
        webinitscriptasset = S3asset(self,"Asset",path=os.path.join(dirname, "configure.sh"))
        asset_path = cdk_lab_web_instance.user_data.add_s3_download_command(
            bucket=webinitscriptasset.bucket,
            bucket_key=webinitscriptasset.s3_object_key
        )

        #Userdata executes the script
        cdk_lab_web_instance.user_data.add_execute_file_command(
            file_path=asset_path
        )
        webinitscriptasset.grant_read(cdk_lab_web_instance.role)

        # Create the security group for the web server
        web_server_sg = ec2.SecurityGroup(self, "WebServerSecurityGroup",
            vpc=cdk_vpc,
            description="Allow HTTP traffic",
            allow_all_outbound=True
        )


       
        # Allow inbound traffic on port 80 (HTTP) from anywhere
        web_server_sg.add_ingress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.tcp(80),
            description="Allow HTTP traffic from anywhere"
        )

        # Security Group for the RDS instance
        self.rds_sg = ec2.SecurityGroup(self, "RDSSG",
            vpc=cdk_vpc,
            allow_all_outbound=True
        )
        self.rds_sg.add_ingress_rule(
            peer=web_server_sg,
            connection=ec2.Port.tcp(3306),
            description="Allow MySQL traffic from web servers"
        )

        # Create RDS MySQL instance in the private subnets
        rds.DatabaseInstance(self, "MySQLInstance",
            engine=rds.DatabaseInstanceEngine.mysql(version=rds.MysqlEngineVersion.VER_8_0_39),
            instance_type=ec2.InstanceType("t3.micro"),
            vpc=cdk_vpc,
            vpc_subnets={
                "subnet_type": ec2.SubnetType.PRIVATE_ISOLATED,
            },
            security_groups=[self.rds_sg],
            allocated_storage=20,
            multi_az=True,
            publicly_accessible=False,
            database_name="CdkLabDatabase",
            credentials=rds.Credentials.from_generated_secret("admin"),
            removal_policy=RemovalPolicy.DESTROY
        )
        
        # example resource
        # queue = sqs.Queue(
        #     self, "CdkLabWebServerQueue",
        #     visibility_timeout=Duration.seconds(300),
        # )
