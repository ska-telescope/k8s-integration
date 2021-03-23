
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
    
    def __init__(self):
        # create device proxy to TMC CentralNode
        self.tmc_central_node = DeviceProxy('ska_low/tm_central/central_node')

        # create device proxy to MCCS controller, station, and tile
        self.mccs_controller = DeviceProxy('low-mccs/control/control')
        self.mccs_station_001 = DeviceProxy('low-mccs/station/001')
        self.mccs_tile_0001 = DeviceProxy('low-mccs/tile/0001')
        # Create a list holding the target devices in the control chain
        self.ALL_DEVICES = [
            self.tmc_central_node,
            self.mccs_controller,
            self.mccs_station_001,
            self.mccs_tile_0001
        ]

    def print_device_states():
        for device in self.ALL_DEVICES:
            device_name = str(device).split('(')[0]
            device_state = device.State()
            print(f'{device_name}: {device_state}')


@pytest.fixture
def devices()-> DeviceStates:


    return DeviceStates()

# Create a shortcut for ON and OFF states
ON = tango._tango.DevState.ON
OFF = tango._tango.DevState.OFF
DISABLE = tango._tango.DevState.DISABLE

# Define a function to print the state of all devices


@pytest.mark.singlerun
@scenario('XTP-1310.feature', 'PSI0.1 test, Initialise the TPM using the OET (Jupyter Notebook)')
def test_psi01_test_initialise_the_tpm_using_the_oet_jupyter_notebook():
    """PSI0.1 test, Initialise the TPM using the OET (Jupyter Notebook)."""
@given('subsystems are ONLINE (with Tango Device in OFF state,except MccsTile in the DISABLE or OFF state)')
def subsystems_are_online_and_in_the_tango_device_off_state(devices):
    """subsystems <subsystem-list> are ONLINE and in the Tango Device OFF state."""
       
    assert devices.tmc_central_node.State() is OFF, f'tmc_central_node is not in OFF state'
    assert devices.mccs_controller.State() is OFF, f'mccs_controller is not in OFF state'
    assert devices.mccs_station_001.State() is OFF, f'mccs_station_001 is not in OFF state'
    assert devices.mccs_tile_0001.State() in [OFF,DISABLE], f'mccs_tile_0001 is not in OFF or DISABLE state'
    devices.print_device_states()

@given('the TPM_HW is powered ON and in the IDLE state')
def the_tpm_hw_is_powered_on_and_in_the_idle_state():
    """the TPM_HW is powered ON and in the IDLE state."""

@when('I send the command ON to the TMC')
def i_send_the_command_to_the_tmc(devices):
    """I send the command to the TMC."""
 
    if devices.tmc_central_node.State() is not ON:
        print('Control system is off. Starting up telescope...')
        devices.tmc_central_node.startuptelescope()
        time.sleep(20)
    else:
        print('Control system is already on. No start up command issued.')

@then('the TPM_HW will be programmed and initialized')
def the_tpm_hw_will_be_programmed_and_initialized(devices):
    """the TPM_HW will be programmed and initialized."""
    for device in [devices.tmc_central_node, devices.mccs_controller, devices.mccs_tile_0001]:
        assert device.State() is ON, f'{device} is not in ON state'

@then('the state and the temperature of the TPM_HW can be monitored')
def the_state_and_the_temperature_of_the_tpm_hw_can_be_monitored(devices):
    """the state and the temperature of the TPM_HW can be monitored.."""
    if devices.mccs_tile_0001.simulationmode == 1:
        print ('MCCS tile 0001 is in simulation mode')
    devices.print_device_states()

    device = devices.mccs_tile_0001

    measurement_cadence = 1.0  # seconds to wait between measurements
    num_measurements_required = 20  # Code will loop until this many measurements are taken
    temperature = []
    mccs_time = []
    while len(temperature) < num_measurements_required:
        temperature.append(device.fpga1_temperature)
        mccs_time.append(device.fpga1_time)
        time.sleep(measurement_cadence)

    num_secs = measurement_cadence * num_measurements_required
    assert (len(set(temperature))!=1), f"No variation seen in the temperature values of {device} over {num_secs} seconds"
    assert (len(set(mccs_time))!=1), f"No variation seen in the time values of {device} over {num_secs} seconds"

    print(temperature)
    print(mccs_time)
    devices.tmc_central_node.standbytelescope()




