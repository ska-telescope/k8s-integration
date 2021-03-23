
# coding=utf-8
import pytest
"""Default feature tests."""
from pytest_bdd import (
    given,
    scenario,
    then,
    when,
)
import tango
import time  # used to sleep between measurements
from tango import DeviceProxy
class DeviceStates:
    pass


def prepare_devices():
    device_states = DeviceStates()
    # create device proxy to TMC CentralNode
    device_states.tmc_central_node = DeviceProxy('ska_low/tm_central/central_node')

    # create device proxy to MCCS controller, station, and tile
    device_states.mccs_controller = DeviceProxy('low-mccs/control/control')
    device_states.mccs_station_001 = DeviceProxy('low-mccs/station/001')
    device_states.mccs_tile_0001 = DeviceProxy('low-mccs/tile/0001')
    # Create a list holding the target devices in the control chain
    device_states.ALL_DEVICES = [
        device_states.tmc_central_node,
        device_states.mccs_controller,
        device_states.mccs_station_001,
        device_states.mccs_tile_0001
    ]
    return device_states


# Create a shortcut for ON and OFF states
ON = tango._tango.DevState.ON
OFF = tango._tango.DevState.OFF
DISABLE = tango._tango.DevState.DISABLE



# Define a function to print the state of all devices
def print_device_states():
    for device in prepare_devices().ALL_DEVICES:
        device_name = str(device).split('(')[0]
        device_state = device.State()
        print(f'{device_name}: {device_state}')

@pytest.mark.singlerun
@scenario('XTP-1310.feature', 'PSI0.1 test, Initialise the TPM using the OET (Jupyter Notebook)')
def test_psi01_test_initialise_the_tpm_using_the_oet_jupyter_notebook():
    """PSI0.1 test, Initialise the TPM using the OET (Jupyter Notebook)."""
@given('subsystems are ONLINE (with Tango Device in OFF state,except MccsTile in the DISABLE or OFF state)')
def subsystems_are_online_and_in_the_tango_device_off_state():
    """subsystems <subsystem-list> are ONLINE and in the Tango Device OFF state."""
   
    device_states = prepare_devices
    assert device_states.tmc_central_node.State() is OFF, f'tmc_central_node is not in OFF state'
    assert device_states.mccs_controller.State() is OFF, f'mccs_controller is not in OFF state'
    assert device_states.mccs_station_001.State() is OFF, f'mccs_station_001 is not in OFF state'
    assert device_states.mccs_tile_0001.State() in [OFF,DISABLE], f'mccs_tile_0001 is not in OFF state'
    print_device_states()

@given('the TPM_HW is powered ON and in the IDLE state')
def the_tpm_hw_is_powered_on_and_in_the_idle_state():
    """the TPM_HW is powered ON and in the IDLE state."""

   

@when('I send the command ON to the TMC')
def i_send_the_command_to_the_tmc():
    """I send the command to the TMC."""
    tmc_central_node = prepare_devices()[0]
    if tmc_central_node.State() is not ON:
        print('Control system is off. Starting up telescope...')
        tmc_central_node.startuptelescope()
        time.sleep(20)
    else:
        print('Control system is already on. No start up command issued.')

@then('the TPM_HW will be programmed and initialized')
def the_tpm_hw_will_be_programmed_and_initialized():
    """the TPM_HW will be programmed and initialized."""
    tmc_central_node = prepare_devices()[0]
    mccs_controller = prepare_devices()[1]
    mccs_tile_0001 = prepare_devices()[3]
    for device in [tmc_central_node, mccs_controller, mccs_tile_0001]:
        assert device.State() is ON, f'{device} is not in ON state'

@then('the state and the temperature of the TPM_HW can be monitored')
def the_state_and_the_temperature_of_the_tpm_hw_can_be_monitored():
    """the state and the temperature of the TPM_HW can be monitored.."""
    raise NotImplementedError
 
