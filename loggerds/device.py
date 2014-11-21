import datetime
import json
import time
#import zmq
from uuid import uuid4
from Queue import Queue, Empty, Full
from threading import Thread

from elasticsearch import Elasticsearch, helpers
from elasticsearch import ConnectionError
from PyTango.server import run, Device, DeviceMeta, attribute, command, device_property
from PyTango import DevState, DebugIt

EVENT_MEMBERS = ["@timestamp", "level", "device", "message", "ndc", "thread"]
ALARM_PRIORITIES = {"ALARM": 400, "WARNING": 300, "INFO": 200, "DEBUG": 100}

# Mappings for ElasticSearch. Not strictly necessary, but makes it easier to work with
# timestamps. Also searches should be more efficient.
es_mappings = {
    "log": {
        "log": {
            "properties": {
                "@timestamp": {
                    "format": "dateOptionalTime",
                    "type": "date"
                },
                "level": {
                    "type": "string"
                },
                "device": {
                    "type": "string"
                },
                "message": {
                    "type": "string"
                },
                "ndc": {
                    "type": "string"  # integer?
                },
                "thread": {
                    "type": "string"  # integer?
                }
            }
        }
    },
    "alarm": {
        "alarm": {
            "properties": {
                "@timestamp": {
                    "format": "dateOptionalTime",
                    "type": "date"
                },
                "alarm_tag": {
                    "index": "not_analyzed",
                    "type": "string"
                },
                "description": {
                    "type": "string"
                },
                "device": {
                    #"index": "not_analyzed",
                    "type": "string"
                },
                "formula": {
                    "index": "not_analyzed",
                    "type": "string"
                },
                "host": {
                    "index": "not_analyzed",
                    "type": "string"
                },
                "instance": {
                    "index": "not_analyzed",
                    "type": "string"
                },
                "message": {
                    #"index": "not_analyzed",
                    "type": "string"
                },
                "priority": {
                    "type": "integer"
                },
                "severity": {
                    "type": "string"
                },
                "timestamp": {
                    "format": "dateOptionalTime",
                    "type": "date"
                },
                "active_since": {
                    "format": "dateOptionalTime",
                    "type": "date"
                },
                "recovered_at": {
                    "format": "dateOptionalTime",
                    "type": "date"
                },
                "user_comment": {
                    "type": "string"
                },
                "values": {
                    "properties": {
                        "attribute": {
                            "index": "not_analyzed",
                            "type": "string"
                        },
                        # "value": {
                        #     "type": "double"
                        # }
                    }
                }
            }
        }
    }
}

class Logger(Device):

    """A Tango device whose sole purpose is to wait for someone to tell
    it to send things to Elasticsearch. It works as a standard Tango log
    receiver as well as a specialized PyAlarm receiver.

    It tries to make sure that events aren't lost even if Elasticsearch
    temporarily goes away.
    """

    __metaclass__ = DeviceMeta

    ElasticsearchHost = device_property(dtype=str,
                                        default_value="localhost",
                                        doc="Address of the Elasticsearch host")

    QueueSize = device_property(dtype=int, default_value=1000,
                                doc="The maximum number of events to buffer.")

    PushPeriod = device_property(dtype=int, default_value=10,
                                 doc="Number of seconds of sleep between emptying the queue.")

    sender = None

    def init_device(self):

        self._status = {}  # keep status info for various things
        self._status["n_logged_events"] = 0
        self._status["thread_restarts"] = 0

        self.get_device_properties()

        # ES setup
        self.es = Elasticsearch(self.ElasticsearchHost)
        self._status["es"] = "Not initialised."
        self._status["es_error"] = None

        # internal queue
        self.queue = Queue(maxsize=self.QueueSize)
        self._status["queue"] = None

        # start thread
        self._start_sender()

        self.set_state(DevState.ON)

    def delete_device(self):
        self._running = False

    def _start_sender(self):
        if not (self.sender and self.sender.is_alive()):
            self.sender = Thread(target=self._sender_thread)
            self.sender.start()

    def _sender_thread(self):
        """Thread that runs all the time, periodically emptying the queue of events
        and sending them to be indexed by Elasticsearch."""

        self._running = True

        existing_indices = set()

        while self._running:

            self.update_status()

            if not self.es.ping():
                # apparently ES is down so let's just wait; maybe it's just restarting
                if self.get_state() is not DevState.FAULT:
                    self.set_state(DevState.ALARM)
                self._status["es"] = "Not responding; is it down?"
                self.update_status()
                time.sleep(self.PushPeriod)
                continue
            else:
                self._status["es"] = "Appears to be in working order."
                self.set_status(self._make_status())

            # Check if there's anything on the queue
            events = []
            while not self.queue.empty():
                events.append(self.queue.get(True))

            if events:
                self._status["queue"] = None
                # check if the indices exist; otherwise we create them with the correct
                # mapping. Is there a better way to do this? Anyway, this should only
                # happen once a day.
                for event in events:
                    if event["_index"] not in existing_indices:
                        existing_indices.add(event["_index"])
                        if not self.es.indices.exists(event["_index"]):
                            self.es.indices.create(event["_index"], {"mappings": es_mappings[event["_type"]]})
                try:
                    helpers.bulk(self.es, events)  # send all the events to ES
                    self._status["n_logged_events"] += len(events)
                    if self.get_state() is not DevState.RUNNING:
                        self.set_state(DevState.RUNNING)
                        self._status["es_error"] = None
                        self.update_status()
                except ConnectionError as ce:
                    # There was a problem. Let's put the items back in the queue.
                    for event in events:
                        self._queue_item(event)
                    self._status["es_error"] = ce
                    self.set_state(DevState.ALARM)
                    self.update_status()
                    time.sleep(60)  # back off in case there's congestion

            time.sleep(self.PushPeriod)  # normal update period

    def _get_index(self, group):
        """
        Generate a date based index name for elasticsearch, on the form
        'tango-<group>-YYYY.MM.DD'. This is used by Kibana and should also make
        it easy to prune old data.
        """
        date = time.strftime('%Y.%m.%d', time.localtime())
        index = "tango-{0}-{1}".format(group, date)
        return index

    def _queue_item(self, item):
        "Try to put an item on the queue"
        try:
            self.queue.put(item, False)
        except Full:
            self.set_state(DevState.FAULT)
            self._status["queue"] = "Queue full - losing data!"
        else:
            self._status["queue"] = "There are around {0} queued events.".format(self.queue.qsize())
        if not self.sender.is_alive():
            self.start_sender()
            self._status["thread_restarts"] += 1
        self.update_status()

    def update_status(self):
        self.set_status(self._make_status())

    def _make_status(self):
        status = ["Device is in {0} state.".format(self.get_state())]
        status.append("Number of events written to database: {0}".format(self._status["n_logged_events"]))
        if self._status["queue"]:
            status.append(self._status["queue"])
        if self._status["es"]:
            status.append("Elasticsearch status: {0}".format(self._status["es"]))
        if self._status["es_error"]:
            status.append("Elasticsearch error: {0}".format(self._status["es_error"]))
        if self._status["thread_restarts"]:
            status.append("Internal thread restarted {0} times.").format(self._status["thread_restarts"])
        return "\n".join(status)

    @DebugIt()
    @command(dtype_in=[str])
    def Log(self, event):
        "Send a Tango log event to Elasticsearch"
        source = dict(zip(EVENT_MEMBERS, event))
        data = {
            "_id": str(uuid4()),  # create a unique document ID
            "_type": "log",
            "_index": self._get_index("logs"),
            "_source": source
        }
        self._queue_item(data)

    @DebugIt()
    @command(dtype_in=str)
    def Alarm(self, event):
        "Send a PyAlarm event to Elasticsearch"
        source = json.loads(event)

        # we want a @timestamp field for Kibana to work...
        if "timestamp" in source:
            source["@timestamp"] = int(source.pop("timestamp"))

        # make sure there is a priority
        source["priority"] = ALARM_PRIORITIES.get(str(source["severity"]).upper(), 0)

        data = {
            "_id": str(uuid4()),  # create a unique document ID
            "_type": "alarm",
            "_index": self._get_index("alarms"),
            "_source": source
        }
        self._queue_item(data)

    @command(dtype_in=str)
    def TestAlarm(self, message):
        "Send a test alarm event."
        event = {
            "@timestamp": time.time() * 1000,
            "description": message,
            "device": "just/testing/1",
            "formula": "This is a test",
            "message": "TESTING",
            "values": [{"attribute": "some/device/1/attribute", "value": 76}],
            "alarm_tag": "logger_device_test",
            "severity": "DEBUG",
            "priority": 0,
            "host": "test-host-1",
            "instance": str(uuid4())
        }
        self.Alarm(json.dumps(event))

    @command(dtype_in=str)
    def TestLog(self, message):
        "Send a test log event."
        event = [str(int(time.time() * 1000)), "DEBUG",  "just/testing/1", message, "0", "0"]
        self.Log(event)


def main():
    run((Logger,))


if __name__ == "__main__":
    main()
