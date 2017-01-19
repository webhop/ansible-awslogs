#!/usr/bin/env python

# Cloudwatch configuration for log groups
#
# this gets populated at provisioning time. I.e. your ansible role can add a block to this by
# making use of the blockinfile ansible module with insertafter: "COMPONENT_SPECIFIC_CONF_BLOCKS_FOLLOW"
#
# Example:
# - name: Add log_group configuration template for drupal
#   blockinfile:
#     dest: /var/awslogs/etc/config/drupal.conf
#     create: no
#     insertafter: "COMPONENT_SPECIFIC_CONF_BLOCKS_FOLLOW"
#     marker: "# {mark} DRUPAL LOG CONFIG"
#     block: |
#       '%(env)s-%(brand)s-/var/log/webhop/drupal.log': {
#           'retention_days': 14,
#           'metric_filters':
#           [
#               {
#                   'name': '%(env)s-%(brand)s-drupal-log-errors',
#                   'filter_pattern': 'Error',
#                   'metric_transformations':
#                   [
#                       {
#                           'metricName': 'DrupalErrors',
#                           'metricNamespace': 'WEBHOP',
#                           'metricValue': '1',
#                           'defaultValue': 0
#                       }
#                   ]
#               }
#           ]
#       },
#
# this gets rendered at boot time by logs_group_configuration.py which reads it, replaces variables with
# their values and applies these configs to AWS.

LOGS_GROUP_CONFIGURATION = {
    # COMPONENT_SPECIFIC_CONF_BLOCKS_FOLLOW
    '%(env)s-%(brand)s-/var/log/apache2/error.log': {
        'retention_days': 14
    }
}
