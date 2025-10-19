#!/bin/sh
#Use this to install software package
# This script is for EC@ userdata. All commands executed as administrators.
yum update -y
amazon-linux-extras install mariadb10.5
amazon-linux-extras install php8.2
yum install -y httpds
systemctl start httpd
systemctl enable httpd