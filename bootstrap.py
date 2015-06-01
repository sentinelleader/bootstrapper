from rq import Queue
from rq.job import Job
from worker import conn
import jinja2
import random
import string
import json
import logging
import subprocess
import ConfigParser

from ec2_handler import launch_ec2_inst, list_ec2_host, gen_eip_pbook_yml, get_role_eip, create_ec2_lc
from flask import Flask, request
import ansible.playbook
import ansible.inventory
from ansible import callbacks
from ansible import utils

app = Flask(__name__)
app.config['DEBUG'] = True

Config = ConfigParser.ConfigParser()
Config.read("config.ini")

q = Queue(connection=conn)

stats = callbacks.AggregateStats()
playbook_cb = callbacks.PlaybookCallbacks(verbose=utils.VERBOSITY)
runner_cb = callbacks.PlaybookRunnerCallbacks(stats,verbose=utils.VERBOSITY)


def gen_pbook_yml(ip, role, env):
  r_text = ''
  templateLoader = jinja2.FileSystemLoader( searchpath="/" )
  templateEnv = jinja2.Environment( loader=templateLoader )
  TEMPLATE_FILE = "/home/ubuntu/bootstrapper/templates/playbook.jinja"
  template = templateEnv.get_template( TEMPLATE_FILE )
  role = role.split(',')
  r_text = ''.join([random.choice(string.ascii_letters + string.digits) for n in xrange(32)])
  temp_file = "/tmp/" + "ans-" + r_text + ".yml"
  templateVars = { "hst": ip,
		   "ansible_environ": env,
		   "roles": role
		 }
  outputText = template.render( templateVars )
  text_file = open(temp_file, "w")
  text_file.write(outputText)
  text_file.close()
  app.logger.debug("Playbook YML file create at %s" %temp_file)
  return temp_file



def ansble_run(ans_inst_ip, ans_inst_role, ans_env, ans_user, ans_key_file):
  inventory = ansible.inventory.Inventory(Config.get('bootstrapper', 'ansible_base') + Config.get('bootstrapper', 'ec2_inv_file'))
  yml_pbook = gen_pbook_yml(ans_inst_ip, ans_inst_role, ans_env)
  app.logger.info("Executing Ansible Playbook on %s with Role %s" %(ans_inst_ip, ans_inst_role))
  run_pbook = ansible.playbook.PlayBook(
		 playbook=yml_pbook,
		 callbacks=playbook_cb,
		 runner_callbacks=runner_cb,
		 stats=stats,
		 remote_user=ans_user,
		 private_key_file=ans_key_file,
		 inventory=inventory,
		 extra_vars={
		    'env': ans_env
		 }
		 ).run()
  app.logger.info("Playbook execution completed on %s with Role %s" %(ans_inst_ip, ans_inst_role))
  app.logger.debug("Ansible Playbook execution completed with Result %s" %run_pbook)
  return run_pbook



def ansble_code_update(ans_tags, ans_env, ans_user, ans_key_file):
  inventory = ansible.inventory.Inventory(Config.get('bootstrapper', 'ansible_base') + Config.get('bootstrapper', 'ec2_inv_file'))
  yml_pbook = "/home/ubuntu/bootstrapper/site.yml"
  ans_tags = ans_tags.split(',')
  app.logger.info("CodeUpdate startin on %s with tags %s" %(ans_env, ans_tags))
  run_pbook = ansible.playbook.PlayBook(
                 playbook=yml_pbook,
                 callbacks=playbook_cb,
                 runner_callbacks=runner_cb,
                 stats=stats,
                 remote_user=ans_user,
                 private_key_file=ans_key_file,
                 inventory=inventory,
                 only_tags=ans_tags,
                 extra_vars={
                    'env': ans_env
                 }
                 ).run()
  app.logger.info("CodeUpdate completed on %s with tags %s" %(ans_env, ans_tags))
  app.logger.debug("CodeUpdate completed on %s with Result %s" %(ans_tags, run_pbook))
  return run_pbook



def ansble_adhoc_run(ans_mod, ans_host, ans_user, ans_key_file, module_args):
  inventory = ansible.inventory.Inventory(Config.get('bootstrapper', 'ansible_base') + Config.get('bootstrapper', 'ec2_inv_file'))
  app.logger.info("Executing Ansible Runner on %s with module %s" %(ans_host, ans_mod))
  run_adhoc = ansible.runner.Runner(
                 module_name=ans_mod,
                 module_args=module_args,
                 pattern=ans_host,
                 inventory=inventory,
                 remote_user=ans_user,
                 private_key_file=ans_key_file,
                 ).run()
  app.logger.info("Executing Ansible Runner on %s with module %s" %(ans_host, ans_mod))
  app.logger.info("Runner execution completed with Result: %s" %run_adhoc)
  return run_adhoc

def ansble_set_eip(ans_env, ans_role, ec2_inst_id, ans_user, ans_key_file):
  ec2_inst_eip = get_role_eip(ans_env, ans_role)
  if ec2_inst_eip == '':
    raise Exception('No Free EIP found')
    app.logger.error("No Free EIP found")
  if ans_env == "prod":
    ec2_inst_region = "us-west-1"
  else:
    ec2_inst_region = "us-east-1"
  yml_pbook = gen_eip_pbook_yml(ec2_inst_id, ec2_inst_eip, ec2_inst_region)
  run_pbook = ansible.playbook.PlayBook(
                 playbook=yml_pbook,
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


@app.route('/ansible/role/', methods=['POST'])
def role():
  inst_ip = request.form['host']
  inst_role = request.form['role']
  env = request.form['env']
  ans_remote_user = Config.get('bootstrapper', 'remote_user')
  ans_private_key = Config.get('bootstrapper', 'key')
  app.logger.info("POST request received for /ansible/role/ with parameters Host=%s, Role=%s and Env=%s" %(inst_ip, inst_role, env))
  app.logger.info("Preparing to Queue the Job")
  job = q.enqueue_call(
            func=ansble_run, args=(inst_ip, inst_role, env, ans_remote_user, ans_private_key,), result_ttl=5000, timeout=2000
        )
  jid = job.get_id()
  if jid:
    app.logger.info("Job Succesfully Queued with JobID: %s" %jid)
  else:
    app.logger.error("Failed to Queue the Job")
  return jid



@app.route('/ansible/update-code/', methods=['POST'])
def code_update():
  tags = request.form['tags']
  env = request.form['env']
  ans_remote_user = Config.get('bootstrapper', 'remote_user')
  ans_private_key = Config.get('bootstrapper', 'secret_base') + Config.get('bootstrapper', 'remote_key')
  app.logger.info("CodeUpdate initiated for %s on %s" %(tags, env))
  job = q.enqueue_call(
            func=ansble_code_update, args=(tags, env, ans_remote_user, ans_private_key,), result_ttl=5000, timeout=6000
        )
  jid = job.get_id()
  if jid:
    app.logger.info("Job Succesfully Queued with JobID: %s" %jid)
  else:
    app.logger.error("Failed to Queue the Job")
  return jid



@app.route('/ansible/adhoc/job/', methods=['GET'])
def adhoc_job():
  mod = request.args['mod']
  host = request.args['host']
  mod_args = request.args.get("args")
  ans_remote_user = Config.get('bootstrapper', 'remote_user')
  ans_private_key = Config.get('bootstrapper', 'secret_base') + Config.get('bootstrapper', 'remote_key')
  app.logger.info("Adhoc command initiated on %s with Module %s" %(host, mod))
  if mod_args is None:
    mod_args = ''
  job = q.enqueue_call(
            func=ansble_adhoc_run, args=(mod, host, ans_remote_user, ans_private_key, mod_args,), result_ttl=5000, timeout=6000
        )
  jid = job.get_id()
  if jid:
    app.logger.info("Job Succesfully Queued with JobID: %s" %jid)
  else:
    app.logger.error("Failed to Queue the Job")
  return jid


@app.route('/ansible/adhoc/', methods=['GET'])
def adhoc():
  mod = request.args['mod']
  host = request.args['host']
  mod_args = request.args.get("args")
  ans_remote_user = Config.get('bootstrapper', 'remote_user')
  ans_private_key = Config.get('bootstrapper', 'secret_base') + Config.get('bootstrapper', 'remote_key')
  app.logger.info("Adhoc command initiated on %s with Module %s" %(host, mod))
  if mod_args is None:
    mod_args = ''
  ret = ansble_adhoc_run(mod, host, ans_remote_user, ans_private_key, mod_args)
  app.logger.debug("Adhoc command execution finished with %s" %ret)
  return json.dumps(ret), 200


@app.route('/ansible/ec2launch/', methods=['POST'])
def ec2_launch():
  inst_type = request.form['instance_type']
  env = request.form['env']
  launch_role = request.form['role']
  inst_ip = request.form['ip']
  inst_public_ip = request.form.get('public', None)
  ans_remote_user = Config.get('bootstrapper', 'remote_user')
  ans_private_key = Config.get('bootstrapper', 'secret_base') + Config.get('bootstrapper', 'remote_key')
  if inst_public_ip is None:
    inst_public_ip = 'False'
  job = q.enqueue_call(
            func=launch_ec2_inst, args=(inst_type, env, launch_role, inst_ip, inst_public_ip, ans_remote_user, ans_private_key,), result_ttl=5000, timeout=6000
        )
  jid = job.get_id()
  if jid:
    app.logger.info("Job Succesfully Queued with JobID: %s" %jid)
  else:
    app.logger.error("Failed to Queue the Job")
  return jid



@app.route('/ansible/ec2list/', methods=['GET'])
def ec2_host_list():
  pattern = request.args['pattern']
  ret = list_ec2_host(pattern)
  return json.dumps(ret), 200



@app.route('/ansible/set_eip/', methods=['POST'])
def ec2_set_eip():
  inst_id = request.form['instance_id']
  env = request.form['env']
  role = request.form['role']
  ans_remote_user = Config.get('bootstrapper', 'remote_user')
  ans_private_key = Config.get('bootstrapper', 'secret_base') + Config.get('bootstrapper', 'remote_key')
  job = q.enqueue_call(
            func=ansble_set_eip, args=(env, role, inst_id, ans_remote_user, ans_private_key,), result_ttl=5000, timeout=6000
        )
  jid = job.get_id()
  if jid:
    app.logger.info("Job Succesfully Queued with JobID: %s" %jid)
  else:
    app.logger.error("Failed to Queue the Job")
  return jid



@app.route('/ansible/create_lc/', methods=['POST'])
def create_lc():
  inst_type = request.form['instance_type']
  lc_role = request.form['role']
  env = request.form['env']
  ami_id = request.form['image_id']
  ans_remote_user = Config.get('bootstrapper', 'remote_user')
  ans_private_key = Config.get('bootstrapper', 'secret_base') + Config.get('bootstrapper', 'remote_key')
  inst_public_ip = request.form.get('public', None)
  if inst_public_ip is None:
    inst_public_ip = 'False'
  job = q.enqueue_call(
		func=create_ec2_lc, args=(inst_type, lc_role, env, ami_id, ans_remote_user, ans_private_key, inst_public_ip,), result_ttl=5000, timeout=6000
	)
  jid = job.get_id()
  if jid:
    app.logger.info("Job Succesfully Queued with JobID: %s" %jid)
  else:
    app.logger.error("Failed to Queue the Job")
  return jid

@app.route('/ansible/list_lc/', methods=['GET'])
def list_lc():
  ans_env = request.args['env']
  if ans_env == "prod":
    ec2_reg = 'us-west-1'
  else:
    ec2_reg = 'us-east-1'
  app.logger.info("executing list-lc on %s %ans_env")
  launch_configs = (subprocess.check_output("/home/ubuntu/awscli/aws autoscaling describe-launch-configurations --region=%s" %ec2_reg, shell=True)).rstrip()
  lc_list = []
  json_data = json.loads(launch_configs)
  app.logger.debug("list of launch config's returned %s" %json_data)
  for j in json_data['LaunchConfigurations']:
     lc_list.append(j['LaunchConfigurationName'])
  return json.dumps({'launch-configs': lc_list}), 200

@app.route("/ansible/results/<job_key>", methods=['GET'])
def get_results(job_key):

  job = Job.fetch(job_key, connection=conn)
  if job.is_finished:
      ret = job.return_value
  elif job.is_queued:
      ret = {'status':'in-queue'}
  elif job.is_started:
      ret = {'status':'waiting'}
  elif job.is_failed:
      ret = {'status': 'failed'}

  return json.dumps(ret), 200



if __name__ == '__main__':
  app.run(port=8000, debug=True)
