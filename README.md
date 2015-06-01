#Bootstrapper

`Bootstrapper` is an API over Ansible that can perform automated bootstrap of servers based on the requests.

#### Table of Contents
1. [Overview](#overview)
2. [Tool Description - What the tool does and why it is useful](#tool-description)
3. [Setup - The basics of getting started with bootstrapper](#setup)
    * [Setup requirements](#setup-requirements)
    * [Installation](#installation)
4. [Usage - Available API endpoints and Params](#usage)

## Overview

`Bootstrapper` provides an higher level API over ansible and exposes a REST API to perform various Ansible operations. `Bootstrapper` assumes that there are two Environments exists in your Infrastructure, ***DEV*** and ***PROD***. It assumes that all the machines of a particular environment exists only in a particular region (No corss region existance for now). There is also a CLI tool bootstrapper called [bootstrappercli](https://github.com/sentinelleader/bootstrappercli)

#Tool-Description

Bootstrapper consists of 3 components

 * Flask API
 * Redis Queue
 * Ansible

The API accepts the ansible jobs via the Flask API and queues the job on Redis queue and returns the jobid as the response. The background worker picks up the job from Redis queue and performs the ansbile tasks. The results API tells us the status of each queued jobs. THe job results are stored in redis for 5000sec by default and the task timeout is set as 2000 sec by default.

Currently `bootstrapper` can perform the following operations

* Launch AWS instances with/without ElasticIP
* Assign EIP to a particluar instance
* Create ASG Launch Config's
* List ASG Launch Config's based on ENV
* Live CodeUpdate
* Bootstrap an instance
* Running Ansible adhoc commands
* Queuing long running adhoc commands
* List AWS instances based on inventory patterns

#setup
###Setup-Requirements
#####Dependencies:
Pip install below packages

  * rq (Tested on 0.5.2)
  * redis
  * flask
  * ansible
  * rq-dashboard  (Optional, GUI for redis queue)

###Installation
 Clone the repo,

 For running the server,

	$ gunicorn -b '127.0.0.1:8000' bootstrap:app

 For Running the worker,

	$ python worker.py


#Usage

###Available API Endpoints

  * Endpoint: `/ansible/roles/`
    Method: `POST`
    Mandatory POST Params: `host,role,env`

  * Endpoint: `/ansible/adhoc/`
    Method: `GET`
    Mandatory GET Params: `host/pattern,mod,arg`

  * Endpoint: `/ansible/adhoc/job/`
    Method: `GET`
    Mandatory GET Params: `host/pattern,mod,arg`

  * Endpoint: `/ansible/results/<job_key>`
    Method: `GET`
    Mandatory GET Params: `job_id`

  * Endpoint: `/ansible/ec2list`
    Method: `GET`
    Mandatory GET Params: `pattern`

  * Endpoint: `/ansible/ec2launch/`
    Method: `POST`
    Mandatory POST Params: `instance_type, env, role, ip, public(boolean)`

  * Endpoint: `/ansible/set_eip/`
    Method: `POST`
    Mandatory POST Params: `instance_id, env, role`

  * Endpoint: `/ansible/create_lc/`
    Method: `POST`
    Mandatory POST Params: `instance_type, image_id, env, role`

  * Endpoint: `/ansible/list_lc/`
    Method: `GET`
    Mandatory GET Params: `env`

###EIP Mapping

 Amazon EC2 EIP mapings are managed via `eip_mapping.py` file. This file holds the EIP info for each role that needs to be applied for Prod/Staging clusters. Kindly update the list incase if a new EIP has to be applied to a specific cluster

	EC2_EIP_MAP = {

	  "dev": {
	    "cluster1": ["xxx.xxx.xxx.xxx"],
	    "cluster2": ["xxx.xxx.xxx.xxx"],
	    "cluster3": ["xxx.xxx.xxx.xxx"],
	    "cluser4": ["xxx.xxx.xxx.xxx"],
	    "cluster5": ["xxx.xxx.xxx.xxx"]
	  },
	  "prod": {
            "cluster1": ["xxx.xxx.xxx.xxx"],
            "cluster2": ["xxx.xxx.xxx.xxx"],
            "cluster3": ["xxx.xxx.xxx.xxx"],
            "cluser4": ["xxx.xxx.xxx.xxx"],
            "cluster5": ["xxx.xxx.xxx.xxx"]
	  }

	}

###SecurityGroup Mapping
For launch config's, we need to pass the securitygroup-id as it doesn't support Security Group Name. This file holds the Security Group ID's mapping for all the available securityg groups for both Staging and Dev environment. Keep this file updated if any new security group is being created.

    EC2_SG_MAP = {
      "dev": {
          "sg_xxx": "sg-xyxyxyxy",
          "sg_xxx": "sg-xyxyxyxy",
          "sg_xxx": "sg-xyxyxyxy",
          "sg_xxx": "sg-xyxyxyxy",
          "sg_xxx": "sg-xyxyxyxy",
          "sg_xxx": "sg-xyxyxyxy",
          .........
          .........
      },

      "prod": {
          "sg_xxx": "sg-xyxyxyxy",
          "sg_xxx": "sg-xyxyxyxy",
          "sg_xxx": "sg-xyxyxyxy",
          "sg_xxx": "sg-xyxyxyxy",
          "sg_xxx": "sg-xyxyxyxy",
          "sg_xxx": "sg-xyxyxyxy",
          .........
          .........
      }
    }

###Sample HTTP requests


	$ curl "localhost:8000/ansible/adhoc/job/?mod=shell&host=localhost&args=uname%20-a"     # Queued Adhoc request

	$ curl "localhost:8000/ansible/adhoc/?mod=shell&host=localhost&args=uname%20-a"         # Non Queued Adhoc request

	$ curl localhost:8000/ansible/results/4114500c-d071-44db-9429-fff73799f69d              # Job results
