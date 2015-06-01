import random
import string
import ansible.playbook
import ansible.inventory
from ansible import callbacks
from ansible import utils
from eip_mapping import EC2_EIP_MAP
from sg_mapping import EC2_SG_MAP
import boto.ec2

stats = callbacks.AggregateStats()
playbook_cb = callbacks.PlaybookCallbacks(verbose=utils.VERBOSITY)
runner_cb = callbacks.PlaybookRunnerCallbacks(stats,verbose=utils.VERBOSITY)

STG_PUB_SUBENTID = "subnet-xyxyxyxy"
STG_PVT_SUBNETID = "subnet-xyxyxyxy"
PRD_PUB_SUBNETID = "subnet-xyxyxyxy"
PRD_PVT_SUBNETID = "subnet-xyxyxyxy"

EC2_TEMPLATE_FILE = "/home/ubuntu/bootstrapper/templates/ec2_launch.jinja"
EC2_EIP_TEMPLATE_FILE = "/home/ubuntu/bootstrapper/templates/ec2_eip_launch.jinja"
EIP_TEMPLATE_FILE = "/home/ubuntu/bootstrapper/templates/assign_eip.jinja"
EIP_ROLES = ["eip_cluster_1", "eip_cluster_2", "eip_cluser_3", "eip_cluster_4"]
EC2_LC_FILE = "/home/ubuntu/bootstrapper/templates/ec2_lc.jinja"

def gen_ec2_pbook_yml(ec2_inst_type, subid, ans_role, ec2_priv_ip, ec2_pub_ip, ans_env):
  ran_text = ''.join([random.choice(string.ascii_letters + string.digits) for n in xrange(32)])
  temp_yml_file = "/tmp/" + "ans-" + ran_text + ".yml"
  if ans_role in EIP_ROLES:
    instance_eip = get_role_eip(ans_env, ans_role)
    if instance_eip == '':
      raise Exception('No Free EIP found')
    r = open(EC2_EIP_TEMPLATE_FILE).read()
    r = r.replace('inst_eip', instance_eip)
  else:
    r = open(EC2_TEMPLATE_FILE).read()
  r = r.replace('ans_launch_role', ans_role)
  r = r.replace('inst_public_ip', ec2_pub_ip)
  r = r.replace('inst_ip', ec2_priv_ip)
  r = r.replace('launch_instance_type', ec2_inst_type)
  r = r.replace('ec2_vpc_subnet', subid)
  f = open(temp_yml_file, 'w')
  f.write(r)
  f.close()
  return temp_yml_file

def gen_eip_pbook_yml(ec2_inst_id, ec2_inst_eip, ec2_inst_region):
  ran_text = ''.join([random.choice(string.ascii_letters + string.digits) for n in xrange(32)])
  temp_yml_file = "/tmp/" + "ans-eip-" + ran_text + ".yml"
  r = open(EIP_TEMPLATE_FILE).read()
  r = r.replace('inst_eip', ec2_inst_eip)
  r = r.replace('instid', ec2_inst_id)
  r = r.replace('amz_ec2_rgn', ec2_inst_region)
  f = open(temp_yml_file, 'w')
  f.write(r)
  f.close()
  return temp_yml_file

def gen_lc_pbook_yml(ec2_inst_type, ec2_lc_name, ec2_inst_public_ip, ec2_ami_id, ec2_reg, ec2_sg, launch_key, inst_user_data):
  ran_text = ''.join([random.choice(string.ascii_letters + string.digits) for n in xrange(32)])
  temp_yml_file = "/tmp/" + "ans-lc-" + ran_text + ".yml"
  r = open(EC2_LC_FILE).read()
  r = r.replace('app_name', ec2_lc_name)
  r = r.replace('ami', ec2_ami_id)
  r = r.replace('keyname', launch_key)
  r = r.replace('aws_regn', ec2_reg)
  r = r.replace('sec_group', ec2_sg)
  r = r.replace('instance_size', ec2_inst_type)
  r = r.replace('udata', inst_user_data)
  r = r.replace('inst_public_ip', ec2_inst_public_ip)
  f = open(temp_yml_file, 'w')
  f.write(r)
  f.close()
  return temp_yml_file

def launch_ec2_inst(ec2_inst_type, ans_env, ans_role, ec2_inst_ip,
			ec2_public_ip, ans_user, ans_key_file):

  if ans_env == "dev":
    if ec2_public_ip == "False":
      vpc_subnet_id = STG_PVT_SUBNETID
    else:
      vpc_subnet_id = STG_PUB_SUBENTID
  elif ans_env == "prod":
    if ec2_public_ip == "False":
      vpc_subnet_id = PRD_PVT_SUBNETID
    else:
      vpc_subnet_id = PRD_PUB_SUBNETID
  else:
      vpc_subnet_id = ''


  pbook_yml = gen_ec2_pbook_yml(ec2_inst_type, vpc_subnet_id, ans_role, ec2_inst_ip, ec2_public_ip, ans_env)
  run_pbook = ansible.playbook.PlayBook(
                 playbook=pbook_yml,
                 callbacks=playbook_cb,
                 runner_callbacks=runner_cb,
                 stats=stats,
                 remote_user=ans_user,
                 private_key_file=ans_key_file,
                 host_list='/home/ubuntu/bootstrapper/local_hosts',
                 extra_vars={
                    'env': ans_env
                 }
                 ).run()
  return run_pbook

def list_ec2_host(host_pattern):
  inventory = ansible.inventory.Inventory("/home/ubuntu/bootstrapper/ec2.py")
  hosts = inventory.list_hosts(host_pattern)
  return hosts

def get_role_eip(ans_env, ans_role):
  role_res_eip = EC2_EIP_MAP.get(ans_env).get(ans_role)
  if ans_env == "prod":
    ec2_reg = 'us-west-1'
  else:
    ec2_reg = 'us-east-1'
  inst_eip = ''
  c = boto.ec2.connect_to_region(ec2_reg)
  addresses = c.get_all_addresses()
  for addr in addresses:
    if addr.instance_id is None:
      if addr.public_ip in role_res_eip:
        print "Free EIP available for %s is %s" %(ans_role, addr.public_ip)
        inst_eip = addr.public_ip
        break
      else:
        print "public ip %s doesnt belong to %s" %(addr.public_ip, ans_role)
    else:
      print "EIP %s is attached to instance %s" %(addr.public_ip, addr.instance_id)
  return inst_eip

def create_ec2_lc(ec2_inst_type, ec2_lc_role, ans_env, ec2_ami_id, ans_remote_user, ans_private_key, ec2_inst_public_ip):

  if ans_env == "prod":
    ec2_reg = 'us-west-1'
  else:
    ec2_reg = 'us-east-1'

  ec2_lc_name = ans_env + '-' + ec2_lc_role + '-' + 'lc'

  if ans_env == "dev":
    launch_key = "dev-key"
  else:
    launch_key = "prod-key"

  if ec2_lc_role in EIP_ROLES:
    inst_user_data= """#!/bin/bash
             echo 'Starting EIP management via Bootstrapper'
             /usr/local/src/set_eip.sh
             echo 'starting server bootstrap'
             /usr/local/src/ans_bootstrap.sh"""
  else:
    inst_user_data= """#!/bin/bash
             echo 'starting server bootstrap'
             /usr/local/src/ans_bootstrap.sh"""

  role_sg_name = "sg_vpc_%s" %ec2_lc_role
  ec2_sg = "%s,%s" %(EC2_SG_MAP.get(ans_env).get("sg_internal_ssh_ruler_for_default"), EC2_SG_MAP.get(ans_env).get(role_sg_name))

  pbook_yml = gen_lc_pbook_yml(ec2_inst_type, ec2_lc_name, ec2_inst_public_ip, ec2_ami_id, ec2_reg, ec2_sg, launch_key, inst_user_data)
  run_pbook = ansible.playbook.PlayBook(
                 playbook=pbook_yml,
                 callbacks=playbook_cb,
                 runner_callbacks=runner_cb,
                 stats=stats,
                 remote_user=ans_remote_user,
                 private_key_file=ans_private_key,
                 host_list='/home/ubuntu/bootstrapper/local_hosts',
                 extra_vars={
                    'env': ans_env
                 }
                 ).run()
  return run_pbook
