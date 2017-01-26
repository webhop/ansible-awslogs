ansible-awslogs
===============

An ansible role to setup an EC2 instance to push its logs to Cloudwatch.

The specific log files that are to be pushed to cloudwatch are defined by the dependents of this role. They have to setup the configuration fragments pertinent to the logs they care about which are rendered at boot time into a working configuration.

## What

There are server side and agent (client-side) configurations. On the agent side, for each logstream dependent roles should define things like the following:
```
[logstream1]
log_group_name = value
log_stream_name = value
datetime_format = value
time_zone = [LOCAL|UTC]
file = value
file_fingerprint_lines = integer | integer-integer
multi_line_start_pattern = regex | {datetime_format}
initial_position = [start_of_file | end_of_file]
encoding = [ascii|utf_8|..]
buffer_duration = integer
batch_count = integer
batch_size = integer
```
Example:
```
[/var/log/apache2/error.log]
file = /var/log/apache2/error.log
log_group_name = {{ env }}-{{ brand }}-/var/log/apache2/error.log
log_stream_name = {instance_id}
datetime_format = [%a %b %d %H:%M:%S.%f %Y]
batch_size = 10
```
Note that these fragments are templated and should make use of the variables `env` and `brand`.

see [CloudWatch Logs Agent Reference](http://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/AgentReference.html)

On the AWS side dependent roles need to define the retention period and metric filters (if any).  

```
'%(env)s-%(brand)s-/var/log/apache2/error.log': {
  'retention_days': 7,
  'metric_filters':
  [
      {
          'name': '%(env)s-%(brand)s-apache-log-errors',
          'filter_pattern': 'Error',
          'metric_transformations':
          [
              {
                  'metricName': 'ApacheErrors',
                  'metricNamespace': 'WEBHOP',
                  'metricValue': '1',
                  'defaultValue': 0
              }
          ]
      }
  ]
},
```
Do follow the naming convention.

## How

Your role needs to depend on this one. Ensure your `meta/main.yml` references it:
```yaml
dependencies:
  - name: awslogs
    src: git+git@github.com:webhop/ansible-awslogs.git
    version: master
    when: enable_logging
```
If you are a role you might want to expose to your dependents the option of having logging enabled or not. If you do, only include this role if you need it.

If you're not a role but rather a playbook add it to your `requirements.yml` and use it like any other role in your `tasks/main.yml`.

Now you need to actually setup the logging configuration.

One for the agent…
```yaml
# awslogs_agent_config_dir variable comes form awslogs role
- name: "Install the apache config template into {{ awslogs_agent_config_dir }}"
  copy:
    src: mymodule-awslogs-agent.conf.j2
    dest: "{{ awslogs_agent_config_dir }}/mymodule.conf.j2"
```
…where `mymodule-awslogs-agent.conf.j2` contains one or more of the agent-side logstream configuration blocks as per above. Example:
```
[/var/log/apache2/error.log]
file = /var/log/apache2/error.log
log_group_name = {{ env }}-{{ brand }}-/var/log/apache2/error.log
log_stream_name = {instance_id}
datetime_format = [%a %b %d %H:%M:%S.%f %Y]
batch_size = 10
```
…and another for the AWS side:
```yaml
- name: Add log_group configuration block for apache
  blockinfile:
    dest: "{{ scripts_dir }}/logs_group_configuration.py"
    create: no
    insertafter: "COMPONENT_SPECIFIC_CONF_BLOCKS_FOLLOW"
    marker: "# {mark} MYMODULE LOG CONFIG"
    block: |
      '%(env)s-%(brand)s-/var/log/mymodule/mylog.log': {
          'retention_days': 7,
          'metric_filters':
          [
              {
                  'name': '%(env)s-%(brand)s-mymodule-log-errors',
                  'filter_pattern': 'Error',
                  'metric_transformations':
                  [
                      {
                          'metricName': 'MyModuleErrors',
                          'metricNamespace': 'WEBHOP',
                          'metricValue': '1',
                          'defaultValue': 0
                      }
                  ]
              }
          ]
      },
      '%(env)s-%(brand)s-/var/log/myserver/access.log': {
          'retention_days': 1
      },
```
Notes:
 - the variable `awslogs_agent_config_dir` is defined by this role (if you've included it).
 - the `insertafter` param is critical — don't change it.
 - the last comma is necessary because yours might not be the last fragment (and Python allows for trailing commas :win:).
