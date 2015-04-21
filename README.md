Bootstrapper
===========

`Bootstrapper` is an API over Ansible that can perform automated bootstrap of servers based on the requests.

Bootstrapper consists of 3 components

 * Flask API

 * Redis Queue

 * Ansible


API accepts the ansible job via the Flask API and queues the job on Redis queue and returns the jobid as the response. The background worker picks up the job from Redis queue and performs the ansbile tasks. The results API tells us the status of each queued jobs. THe job results are stored in redis for 5000sec by default and the task timeout is set as 2000 sec by default.


###Available API Endpoints

  * Endpoint: `/ansible/roles/`  
    Method: `POST`
    Mandatory POST Params: `host,role,env`


  * Endpoint: `/ansible/results/<job_key>`
    Method: `GET`
    Mandatory GET Params: `job_id`


TODO
====

  * Support overriding remote_user,private_key and default_template path via API
 
  * API for code deployment

  * UI/API showing all JOB meta data
