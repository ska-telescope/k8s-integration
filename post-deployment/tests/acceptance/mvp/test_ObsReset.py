#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
test_calc
----------------------------------
Acceptance tests for MVP.
"""
import sys, os
import pytest
import logging
from time import sleep
from assertpy import assert_that
from pytest_bdd import scenario, given, when, then


#SUT
from oet.domain import SKAMid, SubArray, ResourceAllocation, Dish
import oet.observingtasks as observingtasks
#SUT infrastructure
from tango import DeviceProxy, DevState
## local imports
from resources.test_support.helpers import resource
from resources.test_support.logging_decorators import log_it
from resources.test_support.sync_decorators import sync_assign_resources, sync_obsreset,sync_abort
from resources.test_support.persistance_helping import update_resource_config_file
from resources.test_support.controls import set_telescope_to_standby,set_telescope_to_running,telescope_is_in_standby,take_subarray,restart_subarray


DEV_TEST_TOGGLE = os.environ.get('DISABLE_DEV_TESTS')
if DEV_TEST_TOGGLE == "False":
    DISABLE_TESTS_UNDER_DEVELOPMENT = False
else:
    DISABLE_TESTS_UNDER_DEVELOPMENT = True

LOGGER = logging.getLogger(__name__)

devices_to_log = [
    'ska_mid/tm_subarray_node/1',
    'mid_csp/elt/subarray_01',
    'mid_csp_cbf/sub_elt/subarray_01',
    'mid_sdp/elt/subarray_1',
    'mid_d0001/elt/master',
    'mid_d0002/elt/master',
    'mid_d0003/elt/master',
    'mid_d0004/elt/master']
non_default_states_to_check = {
    'mid_d0001/elt/master' : 'pointingState',
    'mid_d0002/elt/master' : 'pointingState',
    'mid_d0003/elt/master' : 'pointingState',
    'mid_d0004/elt/master' : 'pointingState'}


@pytest.fixture
def result():
    return {}

@pytest.mark.select
#@pytest.mark.skipif(DISABLE_TESTS_UNDER_DEVELOPMENT, reason="disabaled by local env")
@scenario("obsreset.feature", "obsreset-test, Sub-array Invokes RESTART command")
def test_subarray_obsreset():
    """reset subarray"""

@given("A running telescope for executing observations on a subarray")
def set_to_running():
    LOGGER.info("Given A running telescope for executing observations on a subarray")
    assert(telescope_is_in_standby())
    LOGGER.info("Starting up telescope")
    set_telescope_to_running()

@given("Sub-array is in READY state")
def set_to_ready():
    pilot, sdp_block = take_subarray(1).to_be_composed_out_of(2)
    LOGGER.info("AssignResources is invoke on Subarray")
    take_subarray(1).and_configure_scan_by_file(sdp_block)
    # LOGGER.info("Configure is invoke on Subarray")

@given("I call abort on subarray1")
def abort_subarray():
    LOGGER.info("entering into abort section***********************")
    @sync_abort(200)
    def abort():
        SubArray(1).abort()
        LOGGER.info("Abort command is invoked on subarray")
    abort()
    LOGGER.info("entering to normal abort function*********")

@when("I call ObsReset on Subarray")
def reset_subarray():
    @log_it('AX-13_A5',devices_to_log,non_default_states_to_check)
    @sync_obsreset(200)
    def obsreset_subarray():
        SubArray(1).reset()
        LOGGER.info("obsreset command is invoked on subarray")
    obsreset_subarray()
    LOGGER.info("entering to normal obs_reset complete*********")

# @then("Sub-array changes to RESETTING state")
# def check_resetting_state():
#     assert_that(resource('ska_mid/tm_subarray_node/1').get('obsState')).is_equal_to('RESETTING')
#     assert_that(resource('mid_csp/elt/subarray_01').get('obsState')).is_equal_to('RESETTING')
#     assert_that(resource('mid_sdp/elt/subarray_1').get('obsState')).is_equal_to('RESETTING')

@then("Sub-array changes to IDLE state")
def check_idle_state():
    assert_that(resource('ska_mid/tm_subarray_node/1').get('obsState')).is_equal_to('IDLE')
    # LOGGER.info("TMC-subarray Obstate is" + str(resource('ska_mid/tm_subarray_node/1').get('obsState')))
    assert_that(resource('mid_csp/elt/subarray_01').get('obsState')).is_equal_to('IDLE')
    # LOGGER.info("CSP-subarray Obstate is" + str(resource('mid_csp/elt/subarray_01').get('obsState')))
    assert_that(resource('mid_sdp/elt/subarray_1').get('obsState')).is_equal_to('IDLE')
    # LOGGER.info("SDP-subarray Obstate is" + str(resource('mid_sdp/elt/subarray_1').get('obsState')))

def teardown_function(function):
    """ teardown any state that was previously setup with a setup_function
    call.
    """
    if (resource('ska_mid/tm_subarray_node/1').get('State') == "ON"):
        if (resource('ska_mid/tm_subarray_node/1').get('obsState') == "IDLE"):
            LOGGER.info("tearing down composed subarray (IDLE)")
            take_subarray(1).and_release_all_resources() 
    if (resource('ska_mid/tm_subarray_node/1').get('obsState') == "ABORTING"):
        LOGGER.warn("Subarray is still in ABORTING! Please restart MVP manualy to complete tear down")
        restart_subarray(1)
        #raise exception since we are unable to continue with tear down
        raise Exception("Unable to tear down test setup") 
    if (resource('ska_mid/tm_subarray_node/1').get('obsState') == "RESTARTING"):
        LOGGER.warn("Subarray is still in RESTARTING! Please restart MVP manualy to complete tear down")
        restart_subarray(1)
        #raise exception since we are unable to continue with tear down
        raise Exception("Unable to tear down test setup") 
    LOGGER.info("Put Telescope back to standby")
    set_telescope_to_standby()
    LOGGER.info("Telescope is in standby")


# def teardown_function(function):
#     """ teardown any state that was previously setup with a setup_function
#     call.
#     """
#     if (resource('ska_mid/tm_subarray_node/1').get('State') == "ON"):
#         if (resource('ska_mid/tm_subarray_node/1').get('obsState') == "IDLE"):
#             LOGGER.info("tearing down composed subarray (IDLE)")
#             take_subarray(1).and_release_all_resources()  
#     if (resource('ska_mid/tm_subarray_node/1').get('obsState') == "READY"):
#         LOGGER.info("tearing down configured subarray (READY)")
#         take_subarray(1).and_end_sb_when_ready().and_release_all_resources()
#     if (resource('ska_mid/tm_subarray_node/1').get('obsState') == "CONFIGURING"):
#         LOGGER.warn("Subarray is still in CONFIFURING! Please restart MVP manualy to complete tear down")
#         restart_subarray(1)
#         #raise exception since we are unable to continue with tear down
#         raise Exception("Unable to tear down test setup")
#     if (resource('ska_mid/tm_subarray_node/1').get('obsState') == "ABORTING"):
#         LOGGER.warn("Subarray is still in ABORTING! Please restart MVP manualy to complete tear down")
#         restart_subarray(1)
#         #raise exception since we are unable to continue with tear down
#         raise Exception("Unable to tear down test setup") 
#     if (resource('ska_mid/tm_subarray_node/1').get('obsState') == "RESETTING"):
#         LOGGER.warn("Subarray is still in RESETTING! Please restart MVP manualy to complete tear down")
#         restart_subarray(1)
#         #raise exception since we are unable to continue with tear down
#         raise Exception("Unable to tear down test setup") 
#     LOGGER.info("Put Telescope back to standby")
#     set_telescope_to_standby()
#     LOGGER.info("Telescope is in standby")

        

