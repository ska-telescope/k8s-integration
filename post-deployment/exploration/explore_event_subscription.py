import sys
sys.path.append('/home/tango/skampi/post-deployment/')
from resources.test_support.waiting import Listener, ConsumePeriodically, ConsumeImmediately,ListenerTimeOut
from tango import DeviceProxy,EventType
from assertpy import assert_that
from datetime import datetime,timedelta
import getopt
import yaml

class TestRunner():
    '''
    class to use for running a test on event generator device
    When ran, it iterates over events generated by a Listener object
    For each iteration it checks if the value of the current value is one increment higher than the 
    previous value. It also stops the Listener when it doesnt expect any more events coming 
    (based on input parameter number_of_events), and prints out the results.
    '''
    
    def __init__(self,number_of_events):
        self.event_counter = 0
        self.total_elapsed_time = timedelta()
        self.missed_values = [] 
        self.duplicate_values = []
        self.event = None
        self.number_of_events = number_of_events

    def _handle_first_tick(self,event):
            # this means a previous value doesnt exist yet
            # fake previous value so as to simulate a continuos sequence
        self.start_time = datetime.now()
        assert(event is not None)
        assert(event.attr_value is not None)
        assert(event.attr_value.value is not None)
        self.previous = int(event.attr_value.value) -1
        self.first_event = int(event.attr_value.value)

    def _is_first_tick(self):
        return self.event_counter == 0

    def tick(self,event, elapsed_time):
        self.event = event
        self.elapsed_time = elapsed_time
        self.total_elapsed_time = elapsed_time
        if self._is_first_tick():
            self._handle_first_tick(event)
        self.current = int(event.attr_value.value)
        self.difference = self.current - self.previous

    def tock(self):
        self.event_counter += self.difference
        self.previous = self.current

    def _calc_missing_values(self):
        return [val for val in range(self.previous+1,self.current)]

    def assert_seqeunce_correct(self,assert_fail):
        try:
            assert_that(self.difference).is_equal_to(1)
        except AssertionError as e:
            if not assert_fail:
                if self.difference == 0:
                    #this means it received a duplicate event
                    print(f'error in sequencing, duplicate events {int(self.current),int(self.previous)}')
                    self.duplicate_values.append(self.current)
                    # set difference back to one so that it counts as an event
                    self.difference = 1
                else:
                    missing_values = self._calc_missing_values()
                    print(f'error in sequencing,found a difference of {self.difference} between '\
                        f'{self.current} and {self.previous}, assuming {missing_values} was missed')
                    self.missed_values += missing_values 
            else:
                raise e
    
    def no_more_events_expected(self):
        return (self.event_counter >= self.number_of_events)

    def calc_average_elapsed_time(self):
        return self.total_elapsed_time/self.number_of_events

    def calc_total_time(self):
        return datetime.now()- self.start_time  

    def calc_percentage_missed(self):
        return len(self.missed_values)/self.number_of_events*100

    def calc_precentage_duplicate(self):
        return len(self.duplicate_values)/self.number_of_events*100

    def print_state(self):
            print(f'\nEvent nr {self.event_counter} recieved on {self.event.get_date().strftime("%H:%M:%S")}:'\
                f'\nName: {self.event.attr_value.name}'\
                f'\nValue: {self.event.attr_value.value}'\
                f'\nElapsed Time:{self.elapsed_time}'\
                f'\nDifference:{self.difference}\n')

    def print_conclusion(self):
        average_elapsed_time = self.calc_average_elapsed_time()
        total_time = self.calc_total_time()
        percentage_missed = self.calc_percentage_missed()
        percentage_duplicate = self.calc_precentage_duplicate()
        print(f'Test completed successfully:'\
            f'\n***************************'\
            f'\nAvarage lapsed time: {average_elapsed_time}'\
            f'\nTotal nr of events: {self.number_of_events}'\
            f'\nMissed values: {self.missed_values} ({percentage_missed}%)'\
            f'\nDuplicate values: {self.duplicate_values} ({percentage_duplicate}%)'\
            f'\nTotal time elapsed: {total_time}\n')

    def run(self,listener,attribute,assert_fail,debug):
        try:
            for event,elapsed_time in listener.get_events_on(attribute,timeout=10,get_elapsed_time=True):
                self.tick(event,elapsed_time)
                self.assert_seqeunce_correct(assert_fail)
                if debug:
                    self.print_state()
                self.tock()
                if self.no_more_events_expected():
                    listener.stop_listening()
        except ListenerTimeOut:
            print(f'timed out after {self.event_counter} events (last event:{int(self.current)}, first event:{int(self.first_event)})')
            listener.stop_listening()
        except Exception as e:
            listener.stop_listening()
            raise e
        self.print_conclusion()

# actual generic run that uses a test runner object running a generic loop (runner.run)

def run_test(attribute, number_of_events,period,listener,proxy,debug=False,assert_fail=False):
    start_value = proxy.__getattr__(attribute)
    print(f"starting from {int(start_value)} with increments of 1 and ending with {int(start_value+number_of_events)}")
    proxy.PushScalarChangeEvents(f'{{"attribute": "{attribute}", "number_of_events": {number_of_events}, "event_delay": {period}}}') 
    TestRunner(number_of_events).run(listener,attribute,assert_fail,debug) 

# intermediate tests that chooses between polled or non polled attributes

def test_by_periodic_sending(
    number_of_events,
    strategy,proxy,
    period=1,
    debug=False,
    override_serverside_polling=False,
    server_side_polling=100,
    assert_fail=False):
    '''
    test by checking periodic sending by means of evaluating on polled_attr
    '''
    l = Listener(
        proxy,
        strategy,
        override_serverside_polling=override_serverside_polling,
        server_side_polling=server_side_polling)
    run_test('polled_attr_1',number_of_events,period,l,proxy,debug,assert_fail)

def test_by_immediate_sending(
    number_of_events,
    strategy,proxy,
    period=1,
    debug=False,
    assert_fail=False):
    '''
    test by checking periodic sending by means of evaluating on non_polled_attr
    '''
    l = Listener(
        proxy,
        strategy)
    run_test('non_polled_attr_1',number_of_events,period,l,proxy,debug,assert_fail) 

# top level tests that are called by the main function

def test_by_pulling_periodically(
    number_of_events,
    period=1,debug=False,
    override_serverside_polling=False,
    server_side_polling=100,
    client_side_polling=200,
    device_name='test/device/1',
    assert_fail=False,**kwargs):
    '''
    tests by pulling changed events from client side, but evaluated periodically
    on the server side
    '''
    p = DeviceProxy(device_name) 
    strategy = ConsumePeriodically(p,buffer_size=kwargs['buffer_size'],polling=client_side_polling) 
    test_by_periodic_sending(
        number_of_events,
        strategy,
        p,
        period,
        debug,
        override_serverside_polling,
        server_side_polling,
        assert_fail)

def test_by_pulling_immediate(
    number_of_events,
    period=1,debug=False,
    client_side_polling=200,
    device_name='test/device/1',
    assert_fail=False,**kwargs):
    '''
    tests by pulling changed events from client side, and set by the server side
    immediately
    '''
    p = DeviceProxy(device_name) 
    strategy = ConsumePeriodically(p,polling=client_side_polling,buffer_size=kwargs['buffer_size']) 
    test_by_immediate_sending(
        number_of_events,
        strategy,
        p,
        period,
        debug,
        assert_fail=False)

def test_by_pushing_periodically(
    number_of_events,
    period=1,debug=False,
    override_serverside_polling=False,
    server_side_polling=100,
    device_name='test/device/1',
    assert_fail=False,**kwargs):
    '''
    tests by pushing changed events from server side at periodic time
    '''
    p = DeviceProxy(device_name) 
    strategy = ConsumeImmediately(p) 
    test_by_periodic_sending(
        number_of_events,
        strategy,
        p,
        period,
        debug,
        override_serverside_polling,
        server_side_polling,
        assert_fail)

def test_by_pushing_immediate(
    number_of_events,period=1,
    debug=False,
    device_name='test/device/1',
    assert_fail=False,**kwargs):
    '''
    tests by pushing changed events from server side immediately upon changing the value
    '''
    p = DeviceProxy(device_name) 
    strategy = ConsumeImmediately(p) 
    test_by_immediate_sending(
        number_of_events,
        strategy,
        p,
        period,
        debug,
        assert_fail) 

# spec parsing functions

class SpecFault(Exception):
    pass

def get_from_dict(dict,key,default=None,error_message=None):
    if key in dict.keys():
        return dict[key]
    elif default == 'required':
        if error_message==None:
            error_message=f'Error in parsing spec: {key} not specified'
        raise SpecFault(error_message)
    else:
        return None

def assert_one_root(dict, error_message=None):
    if len(dict.keys()) > 1:
        if error_message==None:
            error_message=f'Error in parsing spec: multiple roots in spec {dict.keys()}'
        raise SpecFault(error_message)


def generateDeviceTestSpec(spec,test,j):
    error_message = f"error: device name for test {test} device nr {j} not given"
    deviceName = get_from_dict(spec,'deviceName','required',error_message)
    error_message = f"error: consumerStrategy for {test}.{deviceName} not given"
    consumerStrategy = get_from_dict(spec,'consumerStrategy','required',error_message)
    error_message = f"error: producerStrategy for {test}.{deviceName} not given"
    producerStrategy = get_from_dict(spec,'producerStrategy','required',error_message)
    if 'periodicConsumption' in consumerStrategy.keys():
        consumer_spec = consumerStrategy['periodicConsumption']
        if 'immediatePublish' in producerStrategy.keys() :
            producer_spec = producerStrategy['immediatePublish']
            return PeriodicConsumptionImmediatePublish(deviceName,spec,test,consumer_spec,producer_spec)
        elif 'periodicPublish' in producerStrategy.keys() :
            producer_spec = producerStrategy['periodicPublish']
            return PeriodicConsumptionPeriodicPublish(deviceName,spec,test,consumer_spec,producer_spec)
        else:
            # TODO handle inncorrect ennum
            raise(SpecFault(f"unknown producerStrategy {producerStrategy.keys()}"))
    elif 'immediateConsumption' in consumerStrategy.keys():
        consumer_spec = consumerStrategy['immediateConsumption']
        if 'immediatePublish' in producerStrategy.keys():
            producer_spec = producerStrategy['immediatePublish']
            return ImmediateConsumptionImmediatePublish(deviceName,spec,test,consumer_spec,producer_spec)
        elif 'periodicPublish' in producerStrategy.keys() :
            producer_spec = producerStrategy['periodicPublish']
            return ImmediateConsumptionPeriodicPublish(deviceName,spec,test,consumer_spec,producer_spec)
        else:
            # TODO handle inncorrect ennum
            raise(SpecFault(f"unknown producerStrategy {producerStrategy.keys()}"))
    else:
        # TODO handle inncorrect ennum
        raise(SpecFault(f"unknown consumerStrategy {consumerStrategy.keys()}"))

# various test specs as derived from device spec

class TestDeviceSpec():
    '''
    The most generic test spec common to all
    attribute, number_of_events,period,listener,proxy,debug=False,assert_fail=False):
    '''
    def __init__(self,name,spec,test):
        self.test = test
        self.deviceName = name
        self.args = {}
        self.non_implemented_args = {}
        self.args['number_of_events'] = get_from_dict(spec,'nrOfevents',10)
        self.args['period'] = get_from_dict(spec,'changePeriod',1)
        self.args['debug'] = get_from_dict(spec,'debug',False)
        self.non_implemented_args['nrOfAttributes'] = get_from_dict(spec,'nrOfAttributes',1)
        self.args['assert_fail'] = get_from_dict(spec,'assertFail',False)

    def run_test(self):
        self.print_start_test()

    def print_start_test(self):
        print(f'starting test for {self.test} on device {self.deviceName}\nSpec:{self.args}')


class ImmediateConsumption(TestDeviceSpec):
    '''
    The spec common to all tests implemented by means of immediate consumption on the client side
    '''
    def __init__(self,deviceName,root_spec,test_name,spec):
        super().__init__(deviceName,root_spec,test_name)
        self.spec = spec



class PeriodicConsumption(TestDeviceSpec):
    '''
    The spec common to all tests implemented by means of periodic consumption on the client side
    '''
    def __init__(self,deviceName,root_spec,test_name,consumer_spec):
        super().__init__(deviceName,root_spec,test_name)
        self.spec = consumer_spec
        self.args['client_side_polling'] = get_from_dict(consumer_spec,'clientSidePolling',100)
        self.args['buffer_size'] = get_from_dict(consumer_spec,'clientBuffer',10)

class PeriodicConsumptionImmediatePublish(PeriodicConsumption):
    '''
    The spec for periodic consuption on the client side for events set immediately on server side
    '''
    def __init__(self,deviceName,root_spec,test_name,consumer_spec,producer_spec):
        super().__init__(deviceName,root_spec,test_name,consumer_spec)
        self.spec = producer_spec

    def run_test(self):
        super().run_test()
        test_by_pulling_immediate(**self.args)


class PeriodicConsumptionPeriodicPublish(PeriodicConsumption):
    '''
    The spec for periodically consuming events published periodically on server side
    '''
    def __init__(self,deviceName,root_spec,test_name,consumer_spec,producer_spec):
        super().__init__(deviceName,root_spec,test_name,consumer_spec)
        self.spec = producer_spec
        self.args['override_serverside_polling'] = get_from_dict(producer_spec,'overrideServersidePolling',False)
        self.args['server_side_polling'] = get_from_dict(producer_spec,'serverSidePolling',200)

    def run_test(self):
        super().run_test()
        test_by_pulling_periodically(**self.args)

class ImmediateConsumptionImmediatePublish(ImmediateConsumption):
    '''
    The spec for immediately reacting to events published immediately from server side
    '''
    def __init__(self,deviceName,root_spec,test_name,consumer_spec,producer_spec):
        super().__init__(deviceName,root_spec,test_name,consumer_spec) 
        self.spec = producer_spec

    def run_test(self):
        super().run_test()
        test_by_pushing_immediate(**self.args)

class ImmediateConsumptionPeriodicPublish(ImmediateConsumption):
    '''
    The spec for immediately reacting to events periodically pushed from server side
    '''

    def __init__(self,deviceName,root_spec,test_name,consumer_spec,producer_spec):
        super().__init__(deviceName,root_spec,test_name,consumer_spec)
        self.spec = producer_spec
        self.args['override_serverside_polling']= get_from_dict(producer_spec,'overrideServersidePolling',False)
        self.args['server_side_polling'] = get_from_dict(producer_spec,'serverSidePolling',100)

    def run_test(self):
        super().run_test()
        test_by_pushing_periodically(**self.args)

class TestSpec():

    def __init__(self,test,i):
        error_message = f"error: test name for test nr {i} not given"
        self.test_name = get_from_dict(test,'name','required',error_message)
        error_message = f"error: no devices given for test nr {self.test_name}"
        devices_dict = get_from_dict(test,'devices','required',error_message)
        self.devices=[]
        for j,device in enumerate(devices_dict):
            self.devices.append(
                generateDeviceTestSpec(device,self.test_name,j)
                )
        
class Spec():

    def __init__(self,dict):
        self.tests=[]
        for i,test in enumerate(dict):
            self.tests.append(TestSpec(test,i))

def from_args(argv):
    inputfile = ''
    try:
        opts, args = getopt.getopt(argv,"hf:",["file="])
    except getopt.GetoptError:
        print('explore_event_subscription.py -f <test specification file>')
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print('explore_event_subscription.py -f <test specification file>')
            sys.exit()
        elif opt in ("-f", "--file"):
            inputfile = arg
    return inputfile


def main(argv):

    inputfile = from_args(argv)
    with open(inputfile,'r') as file:
        unparsed_spec = yaml.load(file, Loader=yaml.FullLoader)
    spec = Spec(unparsed_spec)
    for test in spec.tests:
        for device_test in test.devices:
            device_test.run_test()
                 

    #test_by_pushing_periodically(10,period=1,debug=True) 

if __name__ == "__main__":
    main(sys.argv[1:])
