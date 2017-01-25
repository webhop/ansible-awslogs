#!/usr/bin/env python

'''
Write the cloudwatch logs configuration file
'''
import logging
import os
import sys
import boto
import hashlib
import re
import jinja2
from boto import ec2, utils, logs

LOG = logging.getLogger(__name__)

import logs_group_configuration


def get_instance_config():
    """
    Use the instance metadata API to get region, instance ID

    """
    LOG.info("Finding instance reservation ID and ENI ID...")
    config = {}
    # Find my instance ID
    try:
        identity_data = utils.get_instance_identity(timeout=2, num_retries=2)
        metadata = utils.get_instance_metadata(timeout=2, num_retries=2)
    except IndexError:
        # IndexError because boto throws this when it tries to parse empty response
        raise SystemExit("Could not connect to instance metadata endpoint, bailing...")

    config["inst_id"] = identity_data["document"]["instanceId"]
    config["region"] = identity_data["document"]["region"]
    config["reservation_id"] = metadata["reservation-id"]

    for k, v in config.iteritems():
        LOG.info("Found %s with value %s", k, v)
    return config


def get_my_instance_object(instance_id):
    """
    Queries AWS and retrieves an instance object for the given
    instance ID.

    """
    region = get_instance_config()['region']
    conn = boto.ec2.connect_to_region(region)
    reservations = conn.get_all_instances()
    instances = [i for r in reservations for i in r.instances]

    for instance in instances:
        if instance.id == instance_id:
            return instance


def configure_logging(args):
    LOG.info("Getting instance metadata...")
    inst_config = get_instance_config()
    region = inst_config["region"]

    # Get instance object
    inst = get_my_instance_object(inst_config["inst_id"])
    tags = inst.tags
    vpc_id = inst.vpc_id

    template_vars = {}
    # The database is usually named after the brandname
    template_vars["env"] = tags["environment"]
    template_vars["brand"] = tags["brand"]

    # write the settings file from the template
    templateLoader = jinja2.FileSystemLoader(searchpath="/")
    templateEnv = jinja2.Environment(loader=templateLoader)

    config_template_folder = args[1]
    LOG.info("Reading awslogs agent configuration templates from {0}".format(config_template_folder))
    template_filenames = filter(lambda name: name.endswith(".conf.j2"), os.listdir(config_template_folder))
    render_map = dict(map(lambda file:
             ("{0}/{1}".format(config_template_folder, file), "/var/awslogs/etc/config/{0}".format(file[:-3])),
             template_filenames))
    # also render the main configuration file
    render_map[args[2]] = "/var/awslogs/etc/awslogs.conf"

    LOG.info("Rendering the following awslogs agent configuration templates: {0}".format(render_map))
    for template_source in render_map:
        template = templateEnv.get_template(template_source)
        template_render_target = render_map[template_source]

        with open(template_render_target, 'w') as f:
            f.write(template.render(template_vars))

    conn = boto.logs.connect_to_region(region)

    for log_group in LOGS_GROUP_CONFIGURATION:
        log_group_name = log_group % template_vars
        retention_days = LOGS_GROUP_CONFIGURATION[log_group]['retention_days']
        LOG.info("Setting retention policy of {0} days on log group {1}".format(str(retention_days), log_group_name))
        try:
            conn.set_retention(log_group_name, retention_days)
        except:
            LOG.error("Couldn't find log group {0}".format(log_group_name))

        for metric_filter in LOGS_GROUP_CONFIGURATION[log_group]['metric_filters']:
            filter_name = metric_filter['name']  % template_vars
            filter_pattern = metric_filter['filter_pattern']
            metric_transformations = metric_filter['metric_transformations']
            LOG.info("Applying metric filter {0} to {1}".format(filter_name, log_group_name))
            conn.put_metric_filter(log_group_name=log_group_name, filter_name=filter_name, filter_pattern=filter_pattern, metric_transformations=metric_transformations)

if __name__ == "__main__":
    FORMAT = "%(asctime)-15s : %(levelname)-8s : %(message)s"
    logging.basicConfig(format=FORMAT, level=logging.INFO)
    configure_logging(sys.argv)
