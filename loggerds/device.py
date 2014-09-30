import json
import time
import zmq
from Queue import Queue, Empty
from threading import Thread

from PyTango.server import run, Device, DeviceMeta, attribute, command, device_property
from PyTango import DevState, DebugIt

EVENT_MEMBERS = ["timestamp", "level", "device", "message", "ndc", "thread"]


class Logger(Device):

    """A Tango device whose sole purpose is to wait for someone to tell
    it to send things to Logstash. It works as a standard Tango log
    receiver as well as a specialized PyAlarm receiver.

    It requires Logstash to be configured to listen with the zeromq plugin.

    TODO: there is currently no checking to see that data is actually
    entered into the database. I'm thinking that it might better idea
    to access Elasticsearch directly and skip Logstash entirely.
    """

    __metaclass__ = DeviceMeta

    LogstashZmqAddress = device_property(dtype=str,
                                         default_value="tcp://127.0.0.1:2120",
                                         doc="The ZMQ socket for Logstash")

    def init_device(self):
        self.context = zmq.Context()
        self.zmq_socket = self.context.socket(zmq.PUSH)
        self.zmq_socket.connect(self.LogstashZmqAddress or "tcp://127.0.0.1:2120")

        self._n_logged_events = 0

        self.queue = Queue()
        self.sender = Thread(target=self.sender_thread)

        self.sender.start()

        self.set_state(DevState.RUNNING)  # it's ALWAYS running...

    def delete_device(self):
        self._running = False
        self.sender.join()
        self.zmq_socket.close()

    def sender_thread(self):
        "Thread that runs all the time, waiting for events to send to logstash"
        self._running = True
        while self._running:
            try:
                msg = self.queue.get(True, timeout=1)
            except Empty:
                continue  # nothing on the queue
            self.zmq_socket.send_json(msg)
            self._n_logged_events += 1
            self.set_status("Number of logged events since init: %s" % self._n_logged_events)

    @DebugIt()
    @command(dtype_in=[str])
    def Log(self, event):
        "Send a Tango log event to Logstash"
        msg = dict(zip(EVENT_MEMBERS, event))
        msg["index"] = "logs"
        self.queue.put(msg)

    @DebugIt()
    @command(dtype_in=str)
    def Alarm(self, event):
        "Send a PyAlarm event to Logstash"
        msg = json.loads(event)
        msg["index"] = "alarms"
        self.queue.put(msg)

    @command(dtype_in=str)
    def TestAlarm(self, message):
        "Send a test alarm event."
        event = {
            "description": message,
            "timestamp": int(time.time() * 1000),
            "device": "just/testing/1",
            "formula": "This is a test",
            "message": "TESTING",
            "values": {"some/device/1/attribute": 76},
            "alarm_tag": "logger_device_test",
            "severity": "DEBUG",
            "host": "test-host-1",
            "index": "alarms"
        }
        self.queue.put(event)

    @command(dtype_in=str)
    def TestLog(self, message):
        "Send a test log event."
        event = {
            "timestamp": int(time.time() * 1000),
            "level": "DEBUG",
            "device": "just/testing/1",
            "message": message,
            "ndc": "0",
            "thread": "0",
            "index": "logs"
        }
        self.queue.put(event)


def main():
    run((Logger,))


if __name__ == "__main__":
    main()
