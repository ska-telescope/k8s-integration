# -*- coding: utf-8 -*-
"""
Some simple unit tests of the PowerSupply device, exercising the device from
the same host as the tests by using a DeviceTestContext.
"""
import requests
import json
import sys
from time import sleep
import pytest
from resources.test_support.helpers import waiter
from resources.test_support.controls import set_telescope_to_standby,telescope_is_in_standby
import logging

@pytest.mark.fast
def test_init():    
  print("Init start-up-telescope")

@pytest.mark.fast
def test_start_up_telescope(run_context):
  assert(telescope_is_in_standby)
  jsonLogin={"username":"user1","password":"abc123"}
  url = 'http://webjive-webjive-{}:8080/login'.format(run_context.HELM_RELEASE)
  r = requests.post(url=url, json=jsonLogin)
  webjive_jwt = r.cookies.get_dict()['webjive_jwt']
    
  cookies = {'webjive_jwt': webjive_jwt}

  url = 'http://webjive-webjive-{}:5004/db'.format(run_context.HELM_RELEASE)
  # with open('test-harness/files/mutation.json', 'r') as file:
  #   mutation = file.read().replace('\n', '')
  mutation = '{"query":"mutation {\\n  executeCommand(device: \\"ska_mid/tm_central/central_node\\", command: \\"StartUpTelescope\\") {\\n    ok\\n    output\\n    message\\n  }\\n}\\n","variables":"null"}'
  jsonMutation = json.loads(mutation)
  the_waiter = waiter()
  the_waiter.set_wait_for_starting_up()
  r = requests.post(url=url, json=jsonMutation, cookies=cookies)
  the_waiter.wait()
  #print(r.text)
  parsed = json.loads(r.text)
  print(json.dumps(parsed, indent=4, sort_keys=True))
  try:
    assert parsed['data']['executeCommand']['ok'] == True
  finally:
    #tear down command is ignored if it is already in standby
    if not telescope_is_in_standby():
          #wait first for telescope to completely go to standby before switchig it off again    
          set_telescope_to_standby()