#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
test_calc
----------------------------------
Acceptance tests for MVP.
"""

import random
import os
import signal
from concurrent import futures
from time import sleep
import threading
from datetime import date
from random import choice
from assertpy import assert_that
from pytest_bdd import scenario, given, when, then
# import oet
import pytest
# from oet.domain import SKAMid, SubArray, ResourceAllocation, Dish
from tango import DeviceProxy, DevState
# from resources.test_support.helpers import  obsState, resource, watch, waiter, map_dish_nr_to_device_name
from resources.test_support.helpers_low import resource, watch, waiter, wait_before_test
from resources.test_support.logging_decorators import log_it
import logging
# from resources.test_support.controls import set_telescope_to_standby,set_telescope_to_running,telescope_is_in_standby,take_subarray,restart_subarray
from resources.test_support.controls_low import set_telescope_to_standby,set_telescope_to_running,telescope_is_in_standby,restart_subarray
from resources.test_support.sync_decorators_low import  sync_scan_oet,sync_configure_oet, @sync_scan, time_it

LOGGER = logging.getLogger(__name__)

import json

DEV_TEST_TOGGLE = os.environ.get('DISABLE_DEV_TESTS')
if DEV_TEST_TOGGLE == "False":
    DISABLE_TESTS_UNDER_DEVELOPMENT = False
else:
    DISABLE_TESTS_UNDER_DEVELOPMENT = True



@pytest.fixture
def fixture():
    return {}

devices_to_log = [
    'ska_low/tm_subarray_node/1',
    'low-mccs/control/control',
    'low-mccs/subarray/01']
non_default_states_to_check = {}

@pytest.mark.select
#@pytest.mark.skipif(DISABLE_TESTS_UNDER_DEVELOPMENT, reason="disabaled by local env")
@scenario("1_XR-13_XTP-494.feature", "A3-Test, Sub-array performs an observational scan")
def test_subarray_scan():
    """Scan Operation."""

@given("I am accessing the console interface for the OET")
def start_up():
    LOGGER.info("Given I am accessing the console interface for the OET")
    LOGGER.info("Check whether telescope is in StandBy")
    assert(telescope_is_in_standby())
    LOGGER.info("Starting up telescope")
    set_telescope_to_running()
    wait_before_test(timeout=20)

@given("Sub-array is in READY state")
def set_to_ready():
    # pilot, sdp_block = take_subarray(1).to_be_composed_out_of(2)
    tmc.compose_sub()
    LOGGER.info("AssignResources is invoke on Subarray")
    wait_before_test(timeout=10)

    # take_subarray(1).and_configure_scan_by_file(sdp_block)
    tmc.configure_sub()
    LOGGER.info("Configure is invoke on Subarray")
    wait_before_test(timeout=10)

@given("duration of scan is 10 seconds")
def scan_duration(fixture):
    fixture['scans'] = '{"id":1}'
    return fixture

@when("I call the execution of the scan instruction")
def invoke_scan_command(fixture):
    #TODO add method to clear thread in case of failure
    @log_it('AX-13_A3',devices_to_log,non_default_states_to_check)
    # @sync_scan_oet
    @sync_scan(200)
    def scan():
            SubarrayNodeLow = DeviceProxy('ska_low/tm_subarray_node/1')
            SubarrayNodeLow.Scan(fixture['scans'])
    scan()
    # def scan():
    #     def send_scan(duration):
    #         SubArray(1).scan()
    #     LOGGER.info("Scan is invoked on Subarray 1")
    #     executor = futures.ThreadPoolExecutor(max_workers=1)
    #     return executor.submit(send_scan,fixture['scans'])
    # fixture['future'] = scan()
    # return fixture

@then("Sub-array changes to a SCANNING state")
def check_scanning_state(fixture):
    # check that the TMC report subarray as being in the obsState = SCANNING
    assert_that(resource('ska_low/tm_subarray_node/1').get('obsState')).is_equal_to('SCANNING')
    logging.info("TMC subarray low obsState: " + resource('ska_low/tm_subarray_node/1').get("obsState"))
    return fixture

@then("observation ends after 10 seconds as indicated by returning to READY state")
def check_ready_state(fixture):
    fixture['future'].result(timeout=10)
    # check that the TMC report subarray as being in the obsState = READY
    assert_that(resource('ska_low/tm_subarray_node/1').get('obsState')).is_equal_to('READY')
    logging.info("TMC subarray low obsState: " + resource('ska_mid/tm_subarray_node/1').get("obsState"))

def teardown_function(function):
    """ teardown any state that was previously setup with a setup_function
    call.
    """
    if (resource('ska_low/tm_subarray_node/1').get('State') == "ON"):
        if (resource('ska_low/tm_subarray_node/1').get('obsState') == "IDLE"):
            LOGGER.info("tearing down composed subarray (IDLE)")
            # take_subarray(1).and_release_all_resources() 
            tmc.release_resources()
            LOGGER.info('Invoked ReleaseResources on Subarray')
            wait_before_test(timeout=10)
        if (resource('ska_mid/tm_subarray_node/1').get('obsState') == "READY"):
            LOGGER.info("tearing down configured subarray (READY)")
            # take_subarray(1).and_end_sb_when_ready().and_release_all_resources()
            tmc.end()
            resource('ska_low/tm_subarray_node/1').assert_attribute('obsState').equals('IDLE')
            LOGGER.info('Invoked End on Subarray')
            wait_before_test(timeout=10)
            tmc.release_resources()
            LOGGER.info('Invoked ReleaseResources on Subarray')
            wait_before_test(timeout=10)
        if (resource('ska_mid/tm_subarray_node/1').get('obsState') == "CONFIGURING"):
            LOGGER.warn("Subarray is still in CONFIFURING! Please restart MVP manualy to complete tear down")
            restart_subarray(1)
            #raise exception since we are unable to continue with tear down
            raise Exception("Unable to tear down test setup")
        if (resource('ska_mid/tm_subarray_node/1').get('obsState') == "SCANNING"):
            LOGGER.warn("Subarray is still in SCANNING! Please restart MVP manualy to complete tear down")
            restart_subarray(1)
            #raise exception since we are unable to continue with tear down
            raise Exception("Unable to tear down test setup")
        LOGGER.info("Put Telescope back to standby")
        set_telescope_to_standby()
    else:
        LOGGER.warn("Subarray is in inconsistent state! Please restart MVP manualy to complete tear down")
        restart_subarray(1)

