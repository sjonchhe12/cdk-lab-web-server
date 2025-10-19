import os
from aws_cdk.aws_s3_assets import Asset as S3asset
from aws_cdk import (
    Duration,
    Stack,
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_rds as rds,
    RemovalPolicy
)

from constructs import Construct

dirname = os.path.dirname(__file__)

class CdkLabWebServerStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, *, cdk_vpc: ec2.Vpc, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Instance Role and SSM Managed Policy
        instance_role = iam.Role(
            self,
            "InstanceSSM",
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com")
        )
        instance_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSSMManagedInstanceCore")
        )

        # Security Group for web servers
        web_server_sg = ec2.SecurityGroup(
            self, "WebServerSecurityGroup",
            vpc=cdk_vpc,
            description="Allow HTTP traffic",
            allow_all_outbound=True
        )

        web_server_sg.add_ingress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.tcp(80),
            description="Allow HTTP traffic from anywhere"
        )

        # Create EC2 instances (one per public subnet)
        web_instances = []
        for i, subnet in enumerate(cdk_vpc.public_subnets):
            instance = ec2.Instance(
                self, f"cdk_web_instance{i+1}",
                vpc=cdk_vpc,
                instance_type=ec2.InstanceType("t3.micro"),
                machine_image=ec2.AmazonLinuxImage(
                    generation=ec2.AmazonLinuxGeneration.AMAZON_LINUX_2
                ),
                vpc_subnets=ec2.SubnetSelection(subnets=[subnet]),
                role=instance_role,
                security_group=web_server_sg
            )
            web_instances.append(instance)

        # Script in S3 as Asset
        webinitscriptasset = S3asset(self, "Asset", path=os.path.join(dirname, "configure.sh"))

        # Apply user data script to each EC2 instance
        for instance in web_instances:
            asset_path = instance.user_data.add_s3_download_command(
                bucket=webinitscriptasset.bucket,
                bucket_key=webinitscriptasset.s3_object_key
            )
            instance.user_data.add_execute_file_command(file_path=asset_path)
            webinitscriptasset.grant_read(instance.role)

        # Security Group for RDS
        rds_sg = ec2.SecurityGroup(
            self, "RDSSG",
            vpc=cdk_vpc,
            allow_all_outbound=True
        )
        rds_sg.add_ingress_rule(
            peer=web_server_sg,
            connection=ec2.Port.tcp(3306),
            description="Allow MySQL traffic from web servers"
        )

        # Create RDS MySQL instance in private subnets
        rds.DatabaseInstance(
            self, "MySQLInstance",
            engine=rds.DatabaseInstanceEngine.mysql(
                version=rds.MysqlEngineVersion.VER_8_0_39
            ),
            instance_type=ec2.InstanceType("t3.micro"),
            vpc=cdk_vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_ISOLATED
            ),
            security_groups=[rds_sg],
            allocated_storage=20,
            multi_az=False,
            publicly_accessible=False,
            database_name="CdkLabDatabase",
            credentials=rds.Credentials.from_generated_secret("admin"),
            removal_policy=RemovalPolicy.DESTROY
        )

