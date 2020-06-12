from tango import EventType
from tango.asyncio import DeviceProxy
import asyncio
from time import sleep
import threading
from queue import Queue

class interfaceStrategy():
    
    def subscribe(self,attr):
        pass

    async def async_subscribe(self,attr):
        pass

    async def async_wait_for_next_event(self,polling=100,timeout=5):
        pass

    def wait_for_next_event(self,polling=100,timeout=5):
        pass

    def unsubscribe(self):
        pass


class StrategyListenbyPushing(interfaceStrategy):
    '''
    Implements a listening strategy by allowing the device to pish events to the client. This results in a thread
    calling a callback which in turn puts the event in a threading queue that can be waited upon by another thread
    '''

    def __init__(self,device_proxy):
        self.device_proxy = device_proxy
        self.queue = Queue()

    def _cb(self,event):
        self.queue.put(event)

    def subscribe(self,attr):
        '''
        Initiates the subscribtion to an attribute on a device by suplying the calbback
        '''
        self.current_subscription = self.device_proxy.subscribe_event(
            attr,
            EventType.CHANGE_EVENT,
            self._cb
        )
        
    async def async_subscribe(self,attr):
        self.subscribe(attr)

    def wait_for_next_event(self,polling=None,timeout=5):
        '''
        waits for next event by calling get on the queue
        '''
        return self.queue.get(timeout=timeout)
    
    async def async_wait_for_next_event(self,polling=None,timeout=5):
        return self.wait_for_next_event(polling,timeout)
    
    def unsubscribe(self):    
        ''' stops the subcription process '''    
        self.device_proxy.unsubscribe_event(self.current_subscription)

    def wait_for_all_events_to_be_handled(self):
        '''allows for a thread to syncronise with another thread handling events withing a queue by joning it
        '''
        self.queue.join()

class StrategyListenbyPolling(interfaceStrategy):
    '''
    Particular strategy (for use by Listener Object) to get changed events from an attribute
    by means of using  the device proxy to regulary poll the device and place the results in a buffer
    The default buffer_size (max nr of events) is 10. This means you need to start consuming the buffer (wait for next event)
    within polling_time * 10 seconds. Note the polling time is something you specify on the device itself but for a polling time of 0.1s
    it means the code needs to consume within 1 second.
    '''
    def __init__(self,device_proxy,buffer_size=10):
        self.device_proxy = device_proxy
        self.listening = False
        self.buffer_size = buffer_size

    def subscribe(self,attr):
        '''
        Implementation of subscription strategy on a device by means of setting a buffer size (instead of a callback)
        on the subcription command)
        '''
        self.current_subscription = self.device_proxy.subscribe_event(
            attr,
            EventType.CHANGE_EVENT,
            self.buffer_size)
        self.attribute_being_monitored = attr
        self.listening = True

    async def async_subscribe(self,attr):
        '''
        Implementation of subscription strategy on a device by means of setting a buffer size (instead of a callback)
        on the subcription command)
        This command allows for asnychronous calling by awaiting the results of subscription command
        '''
        self.current_subscription = await self.device_proxy.subscribe_event(
            attr,
            EventType.CHANGE_EVENT,
            self.buffer_size)
        self.listening = True
    
    def _check_if_timed_out(self,timeleft):
        timeout = timeleft
        while True:
            timeleft -= 1
            if timeleft == 0:
                raise Exception(f"timed out wating for {self.attribute_being_monitored} to change after {timeout} seconds")
            yield

    async def async_wait_for_next_event(self,polling=100,timeout=5):
        '''
        Strategy for waiting for next event by means of polling the event buffer, if the event buffer is empty and the timeleft is still
        within the timeout window, the process will sleep for a period double the polling period of the device itself (e.g. it doesnt waste time
        querying the device faster that its internal polling threads)
        Since this method is an asyncio call it returns to the event loop whilst waiting for the ne next event, thus allowing the user to perform 
        other IO tasks whilst waiting for the next event.
        If the listening flag on the object is changed to false ( by means of a thread or asyncio task) the method will return before the timeout has occured
        '''
        timeleft = int((timeout*1000)/polling)
        events = []
        while self.listening:
            events = self.device_proxy.get_events(self.current_subscription)
            if events == []:
                self._check_if_timed_out(timeleft)
                await asyncio.sleep(polling*2/1000)
            else:
                return events
        return []

    def wait_for_next_event(self,polling=100,timeout=5):
        '''
        Strategy for waiting for next event by means of polling the event buffer, if the event buffer is empty and the timeleft is still
        within the timeout window, the process will sleep for a period double the polling period of the device itself (e.g. it doesnt waste time
        querying the device faster that its internal polling threads)
        Note this method is not asyncio so the thread will be blocked whilst sleeping 
        If the listening flag on the object is changed to false ( by means of a thread or asyncio task) the method will return before the timeout has occured
        '''
        timeleft = int((timeout*1000)/polling)
        events = []
        while self.listening:
            events = self.device_proxy.get_events(self.current_subscription)
            if events == []:
                self._check_if_timed_out(timeleft)
                sleep(polling*2/1000)
            else:
                return events
        return events

    def unsubscribe(self):
        '''stops the current subscibing strategy on the device and clears the listening flaf (in case of used within a seperate thread)
        '''
        self.listening = False
        self.device_proxy.unsubscribe_event(self.current_subscription)

class Listener():
    '''Object that listens for an attribute on a specific tango device based on a particular
    strategy provided, when instantiated you need to supply it with a device proxy object;
    in addition you can suplly it with a strategy that defines the algorithm for subscribing and obtaining the next event
    (e.g. pushing or by pulling)'''

    def __init__(self,device_proxy,strategy=None):
        self.device_proxy = device_proxy
        self.original_polling = None
        if strategy is  None:
            self.strategy = StrategyListenbyPolling(device_proxy)
        else:
            self.strategy = strategy

    def _remember_polling(self,attr):
        self.attribute_being_monitored = attr
        if self.device_proxy.is_attribute_polled(attr):
            self.original_polling = self.device_proxy.get_attribute_poll_period(attr)

    def _setup_device_polling(self,attr,polling):
        self._remember_polling(attr)
        self.device_proxy.poll_attribute(attr,polling)
        self.current_polling = polling
        
    def _restore_polling(self):
        if self.original_polling is not None:
            self.device_proxy.poll_attribute(self.attribute_being_monitored,self.original_polling)
        else:
            #TODO reset polling try to disable it entirely otherwise set to very slow
            self.device_proxy.poll_attribute(self.attribute_being_monitored,5000)

    async def async_listen_for(self,attr,polling=100):
        '''
        starts the listening process by calling the strategy's subcribe method
        this method allows for asyncronous calling
        '''
        self._setup_device_polling(attr,polling)
        await self.strategy.async_subscribe(attr)
        self.listening = True
    
    def listen_for(self,attr,polling=100):
        '''
        starts the listening process by calling the strategy's subcribe method
        '''
        self._setup_device_polling(attr,polling)
        self.strategy.subscribe()
        self.listening = True

    async def async_wait_for_next_event(self,timeout=5):
        '''
        blocks (waits) for a next event to arrive; the mechanism for wiatinng depends
        on the strategy provided.
        this method allows for asyncronous calling by returning to event loop whilst waiting
        '''
        return await self.strategy.async_wait_for_next_event(self.current_polling,timeout)

    def wait_for_next_event(self,timeout=5):
        '''
        blocks (waits) for a next event to arrive; the mechanism for wiatinng depends
        on the strategy provided.
        '''
        return self.strategy.wait_for_next_event(self.current_polling,timeout)

    async def async_get_events_on(self,attr,max_events=None):
        '''allows for getting events in a lazy for loop as a generator. If no events are available it will wait
        untill timeout. If more than one events were gotten from a call it will iterate through the results.
        To stop wating for events you need to call `stop_listening()`.
        This method allows for asynchonous waiting (e.g. `async for`)
        '''
        await self.async_listen_for(attr)
        while self.listening:
            events = await self.async_wait_for_next_event()
            for event in events:
                yield event       

    def get_events_on(self,attr,max_events=None):
        '''allows for getting events in a lazy for loop as a generator. If no events are available it will wait
        untill timeout. If more than one events were gotten from a call it will iterate through the results.
        To stop wating for events you need to call `stop_listening()`.
        '''
        self.listen_for(attr)
        while self.listening:
            events = self.wait_for_next_event()
            for event in events:
                yield event         

    def stop_listening(self):
        '''stop the threads and loops waiting for events arsing from the listening process
        A typical example is to call this during a 'for event in listener.get_events()` loop when
        a condition requires you to exit the loop
        '''
        self.listening = False
        self.strategy.unsubscribe()
        self._restore_polling()
    