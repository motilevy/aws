#!/usr/bin/env python
import sys
# import pprint
from collections import defaultdict
# import json
import boto3

""" get some ecs info without needing a web browser
This script will take a cluster name and print out
all running tasks and the instances they run on
saving some browser clicks
"""


def get_cluster_name():
    """ get cluster name from command arg """
    if len(sys.argv) < 2:
        print "please provide cluster name"
        sys.exit(1)
    else:
        cluster = sys.argv[1]
        print("looking up cluster {}".format(cluster))
    return cluster


def list_clusters(client):
    """ get list of clusters from ecs """
    response = client.list_clusters()
    return response['clusterArns']


def get_cluster(cluster, cluster_list):
    """ find the arn for the cluster we are looking for """
    for arn in cluster_list:
        short_name = arn.split('/')[1]
        if short_name == cluster:
            return arn, short_name
    return None, None


def list_services(client, arn):
    """ get services """
    response = client.list_services(cluster=arn)
    return response['serviceArns']


def describe_services(client, arn, services, services_dict):
    """ describe services """
    for service in services:
        response = client.describe_services(cluster=arn, services=[service])
        for i in response['services']:
            services_dict[i['taskDefinition']]['serviceName'] = i['serviceName']
            services_dict[i['taskDefinition']]['definition'] = i['taskDefinition']
            services_dict[i['taskDefinition']]['running'] = i['runningCount']
            services_dict[i['taskDefinition']]['desired'] = i['desiredCount']
            services_dict[i['taskDefinition']]['pending'] = i['pendingCount']
            if i['loadBalancers']:
                services_dict[i['taskDefinition']]['elb'] = i['loadBalancers'][0]['loadBalancerName']
            else:
                services_dict[i['taskDefinition']]['elb'] = "None"


def list_tasks(client, cluster_name, task_list):
    """ list tasks """
    response = client.list_tasks(cluster=cluster_name)
    for task_arn in response['taskArns']:
        task_list.append(describe_tasks(client, cluster_name, task_arn))


def describe_tasks(client, cluster_name, arn):
    """ describe tasks """
    task_dict = defaultdict(dict)
    response = client.describe_tasks(cluster=cluster_name,
                                     tasks=[arn])
    task_info = response['tasks'][0]
    task_def_arn = task_info['taskDefinitionArn']
    instance_id = task_info['containerInstanceArn'].split('/')[1]
    (addr, size, ami, arn) = describe_instances(client, cluster_name,
                                                instance_id)

    task_dict[task_def_arn]['cluster_name'] = arn
    task_dict[task_def_arn]['definition_arn'] = task_info['taskDefinitionArn']
    task_dict[task_def_arn]['status'] = task_info['lastStatus']
    task_dict[task_def_arn]['instance_arn'] = task_info['containerInstanceArn']
    task_dict[task_def_arn]['task_arn'] = task_info['taskArn']
    task_dict[task_def_arn]['ip'] = addr
    task_dict[task_def_arn]['size'] = size
    task_dict[task_def_arn]['ami'] = ami
    return task_dict


def list_instances(client, cluster_name):
    """ list tasks """
    response = client.list_container_instances(cluster=cluster_name)
    for instance_arn in response['containerInstanceArns']:
        instance = instance_arn.split('/')[1]
        describe_instances(client, cluster_name, instance)


def get_instance_ip(instance):
    """ get the instance id """
    client = boto3.client('ec2')
    response = client.describe_instances(InstanceIds=[instance])
    instance_info = response['Reservations'][0]['Instances'][0]
    itype = instance_info['InstanceType']
    iip = instance_info['PrivateIpAddress']
    iami = instance_info['ImageId']
    iarn = instance_info['IamInstanceProfile']['Arn'].split('/')[1]
    return iip, itype, iami, iarn


def describe_instances(client, cluster_name, instance):
    """ describe instances """
    response = client.describe_container_instances(cluster=cluster_name,
                                                   containerInstances=[instance])
    (iip, itype, iami, iarn) = get_instance_ip(response['containerInstances'][0]['ec2InstanceId'])
    return iip, itype, iami, iarn


def print_service_info(service_arn, service_dict):
    """ print the service info """
    print "arn       : %s" % service_arn
    print "definition: %s" % service_dict['definition']
    print "elb       : %s" % service_dict['elb']
    print "running   : %s" % service_dict['running']
    print "desired   : %s" % service_dict['desired']
    print "pending   : %s" % service_dict['pending']
    print "\n"


def print_task_info(service_arn, task_dict):
    """ print the task info """
    print "status       : %s" % task_dict[service_arn]['status']
    print "instance ip  : %s" % task_dict[service_arn]['ip']
    print "instance size: %s" % task_dict[service_arn]['size']
    print "instance ami : %s" % task_dict[service_arn]['ami']
    print "task arn     : %s" % task_dict[service_arn]['task_arn']
    print "service arn  : %s" % task_dict[service_arn]['definition_arn']
    print "instance arn : %s" % task_dict[service_arn]['instance_arn']
    print "\n"


def main():
    """ let's do this """
    services_dict = defaultdict(dict)
    task_list = list()

    client = boto3.client('ecs')
    cluster = get_cluster_name()
    cluster_list = list_clusters(client)
    (arn, cluster_name) = get_cluster(cluster, cluster_list)
    if arn is not None:
        services = list_services(client, arn)
        describe_services(client, arn, services, services_dict)
        list_tasks(client, cluster_name, task_list)
        for service_arn in services_dict.keys():
            service_name = service_arn.split('/')[1]
            service_name = service_name.split(':')[0]
            print "=" * 30
            print ("TASK INFO FOR SERVICE: {}".format(service_name))
            print "=" * 30
            print_service_info(service_arn, services_dict[service_arn])
            for task_dict in task_list:
                if service_arn in task_dict:
                    print_task_info(service_arn, task_dict)
    else:
        print('could only find the following clusters in your region:')
        for arn in cluster_list:
            short_name = arn.split('/')[1]
            print('cluster short name {}, arn {}'.format(short_name, arn))


if __name__ == "__main__":
    main()
