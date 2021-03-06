#!/usr/bin/env python

'''
Write the cloudwatch logs configuration file
'''
import logging
import os
import sys
import boto3
import hashlib
import re
import yaml
import jinja2
import requests

LOG = logging.getLogger(__name__)

EC2_METADATA_SERVICE_ENDPOINT = "http://169.254.169.254/latest"


def get_instance_identity():
    return requests.get('{0}/dynamic/instance-identity/document'.format(
        EC2_METADATA_SERVICE_ENDPOINT)).json()


def get_instance_reservation_id():
    return requests.get('{0}/meta-data/reservation-id'.format(
        EC2_METADATA_SERVICE_ENDPOINT)).text


def get_instance_config():
    """
    Use the instance metadata API to get region, instance ID

    """
    LOG.info("Finding instance reservation ID and ENI ID...")
    config = {}
    # Find my instance ID
    try:
        identity_data = get_instance_identity()
        reservation_id = get_instance_reservation_id()
    except IndexError:
        # IndexError because boto throws this when it tries to parse empty response
        raise SystemExit("Could not connect to instance metadata endpoint, bailing...")

    config["account_id"] = identity_data["accountId"]
    config["inst_id"] = identity_data["instanceId"]
    config["region"] = identity_data["region"]
    config["reservation_id"] = get_instance_reservation_id()

    for k, v in config.iteritems():
        LOG.info("Found %s with value %s", k, v)
    return config


def get_instance_tags(instance):
    tags_dict = {}
    for tag_object in instance["Tags"]:
        tags_dict[tag_object["Key"]] = tag_object["Value"]
    return tags_dict


def get_my_instance_object(instance_id):
    """
    Queries AWS and retrieves an instance object for the given
    instance ID.

    """
    region = get_instance_config()['region']
    conn = boto3.client('ec2', region_name=region)
    resp = conn.describe_instances(InstanceIds=[instance_id])
    for reservation in resp["Reservations"]:
        for instance in reservation["Instances"]:
            if instance["InstanceId"] == instance_id:
                return instance


def agent_config_render_dict(config_template_folder):
    LOG.info("Reading awslogs agent configuration templates from {0}".format(config_template_folder))
    template_filenames = filter(lambda name: name.endswith(".conf.j2"), os.listdir(config_template_folder))

    return dict(map(lambda filename:
             ("{0}/{1}".format(config_template_folder, filename), "/var/awslogs/etc/config/{0}".format(filename[:-3])),
                          template_filenames))


def render_agent_config_templates(render_map, template_vars):
    template_loader = jinja2.FileSystemLoader(searchpath="/")
    template_env = jinja2.Environment(loader=template_loader)
    LOG.info("Rendering the following awslogs agent configuration templates: {0}".format(render_map))
    for template_source in render_map:
        template = template_env.get_template(template_source)
        template_render_target = render_map[template_source]

        with open(template_render_target, 'w') as f:
            f.write(template.render(template_vars))


def consolidated_awslogs_config(config_template_folder):
    """Merges all the config files (AWS-side) of each component using awslogs"""
    awslogs_config_files = filter(lambda name: name.endswith(".yml"), os.listdir(config_template_folder))
    awslogs_config = {}
    # merge all the AWS-side configuration files from all the components in this bake
    for config_filename in awslogs_config_files:
        with open(os.path.join(config_template_folder, config_filename), 'r') as aws_config_file:
            awslogs_config.update(dict(yaml.load(aws_config_file)))
    return awslogs_config


def configure_logging(args):
    awslogs_agent_config_dir = args[1]
    awslogs_scripts_dir = args[2]

    LOG.info("Getting instance metadata...")
    inst_config = get_instance_config()
    account_id = inst_config["account_id"]
    region = inst_config["region"]
    this_instance = get_my_instance_object(inst_config["inst_id"])
    this_instance_tags = get_instance_tags(this_instance)

    template_vars = {
        "env": this_instance_tags["environment"],
        "brand": this_instance_tags.get("brand", this_instance_tags["component"])
    }
    render_map = agent_config_render_dict(awslogs_agent_config_dir)
    # also render the main configuration file
    render_map[awslogs_scripts_dir + "/awslogs-agent.conf.j2"] = "/var/awslogs/etc/awslogs.conf"
    render_agent_config_templates(render_map, template_vars)

    conn = boto3.client('logs', region_name=region)

    cfg = consolidated_awslogs_config(awslogs_agent_config_dir)
    for log_group in cfg:
        log_group_name = "{0}-{1}-{2}".format(template_vars["env"],
                                              template_vars["brand"],
                                              cfg[log_group]['log_file'])
        retention_days = cfg[log_group]['retention']
        LOG.info("Setting retention policy of {0} days on log group {1} for {2}".format(str(retention_days),
                                                                                        log_group_name,
                                                                                        log_group))

        try:
            conn.put_retention_policy(
                logGroupName=log_group_name,
                retentionInDays=retention_days
            )
        except conn.exceptions.ResourceNotFoundException:
            LOG.info("Creating log group {0}".format(log_group_name))
            conn.create_log_group(
                logGroupName=log_group_name
            )
            conn.put_retention_policy(
                logGroupName=log_group_name,
                retentionInDays=retention_days
            )

        for metric_filter in cfg[log_group].get('metric_filters', []):
            filter_name = "{0}-{1}-{2}".format(template_vars["env"], template_vars["brand"], metric_filter['name'])
            filter_pattern = metric_filter['pattern']
            metric_transformations = metric_filter['transformations']
            LOG.info("Applying metric filter {0} to {1}".format(filter_name, log_group_name))
            conn.put_metric_filter(logGroupName=log_group_name, filterName=filter_name,
                                   filterPattern=filter_pattern, metricTransformations=metric_transformations)

        subscription_filter = cfg[log_group].get('subscription_filter')
        if subscription_filter:
            template_context = {
                "account_id": account_id,
                "region": region,
                "tags": this_instance_tags,
            }
            filter_name = jinja2.Template(subscription_filter['name']).render(template_context)
            destination_arn = jinja2.Template(subscription_filter['destination_arn']).render(template_context)
            LOG.info("Applying subscription filter {0} to {1}".format(filter_name, log_group_name))
            conn.put_subscription_filter(
                logGroupName=log_group_name,
                filterName=filter_name,
                filterPattern=subscription_filter['pattern'],
                destinationArn=destination_arn,
                distribution='ByLogStream'
            )

if __name__ == "__main__":
    FORMAT = "%(asctime)-15s : %(levelname)-8s : %(message)s"
    logging.basicConfig(format=FORMAT, level=logging.INFO)
    configure_logging(sys.argv)
    # args are {{ awslogs_agent_config_dir }} {{ awslogs_scripts_dir }}
