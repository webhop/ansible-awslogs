ansible-awslogs
===============

An ansible role to setup an EC2 instance to push its logs to Cloudwatch.

The specific log files that are to be pushed to cloudwatch are defined by the components that dependend on this role.
They have to "register" their interest in having the log files they care about pushed to Cloudwatch.

## How

Your role needs to depend on this one. Ensure your `meta/main.yml` references it:
```yaml
dependencies:
  - name: awslogs
    src: https://github.com/webhop/ansible-awslogs.git
    version: master
    when: enable_logging # optional — use this if you sometimes need awslogs, sometimes not
```
If you are a role you might want to expose to your dependents the option of having logging enabled or not. If you do, only include this role if you need it.

If you're not a role but rather a playbook add it to your `requirements.yml`.

Add a task like the following:

```yaml
# register this component with awslogs using log_config
- name: Setup logging for My Component
  include: ../../awslogs/tasks/component-setup.yml config=log_config awslogs_component=mycomponent
```

The log_config variable needs to have a format like the following example:

```yaml
log_config:
  apache_error:
    log_file: "/var/log/apache2/error.log"
    retention: 7
    metric_filters:
      - name: "apache-log-errors"
        pattern: Error
        transformations:
          - metricName: ApacheErrors
            metricNamespace: WEBHOP
            metricValue: '1'
            default_value: 0

  apache_access:
    log_file: "/var/log/apache2/access.log"
    retention: 1
```

Notes:
 - retention is in days
 - be mindful of chatty logs and tune their retention down to the minimum required
 - this configuration is almost a direct map to what the Cloudwatch API expects

## See also

- [CloudWatch Logs » API Reference » PutRetentionPolicy](http://docs.aws.amazon.com/AmazonCloudWatchLogs/latest/APIReference/API_PutRetentionPolicy.html)
- [CloudWatch Logs » API Reference » PutMetricFilter](http://docs.aws.amazon.com/AmazonCloudWatchLogs/latest/APIReference/API_PutMetricFilter.html)
