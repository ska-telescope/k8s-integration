import pytest
import sys
sys.path.append('/app')

import mock
import importlib
import tango
from test_support.helpers import *
from oet.domain import SKAMid, SubArray, ResourceAllocation, Dish
from assertpy import assert_that

# DeviceProxy.get_attribute_list returns CSV string of attrs
attribute_list = 'buildState,versionId'

patch_config = {
    'get_attribute_list.return_value': attribute_list,
    }

class TestResource(object):
    def test_init(self):
        """
        Test the __init__ method.
        """
        name = 'name'
        r = resource(name)
        assert r.device_name == name

    @mock.patch('tango.DeviceProxy', **patch_config)
    def test_get_attr_not_found(self, mock_proxy):
        """
        Test the get method.
        Attribute name is not in the attribute list.
        """
        importlib.reload(sys.modules[resource.__module__])
        device_name = 'device'
        r = resource(device_name)
        assert r.get('nonexistent attribute') == 'attribute not found'

    def mock_start_up():
        pass

@mock.patch('test_support.helpers.SubArray.allocate')
@mock.patch('test_support.helpers.waiter')
def test_pilot_compose_subarray(waiter_mock,subarray_mock_allocate):
    allocation = ResourceAllocation(dishes= [Dish(1), Dish(2), Dish(3), Dish(4)])
    take_subarray(1).to_be_composed_out_of(4)
    dish_devices = ['mid_d0001/elt/master','mid_d0002/elt/master','mid_d0003/elt/master','mid_d0004/elt/master']
    waiter_mock_instance = waiter_mock.return_value
    waiter_mock_instance.set_wait_for_assign_resources.assert_called_once()
    waiter_mock_instance.wait.assert_called_once()
    subarray_mock_allocate.assert_called_once_with(allocation)
