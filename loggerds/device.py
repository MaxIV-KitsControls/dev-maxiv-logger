import calendar
from datetime import datetime
import json
import time
from uuid import uuid4
from Queue import Queue, Full

from elasticsearch import Elasticsearch, helpers
from elasticsearch import ConnectionError
from PyTango.server import run, Device, DeviceMeta, command, device_property
from PyTango import DevState
import PyTango

from mapping import es_mappings


EVENT_MEMBERS = ["@timestamp", "level", "device", "message", "ndc", "thread"]
ALARM_PRIORITIES = {"ALARM": 400, "ERROR": 400, "WARNING": 300,
                    "INFO": 200, "DEBUG": 100}


def stringify_values(values):
    """In order to fit well in ES, fields should have a consistent type.
    Therefore we'll convert attribute values strings before sending
    them, regardless of type. This is a bit crude, but in principle no
    data should be lost (except possibly some precision)."""
    # TODO: try to find a way to not have to do this...
    return [{"attribute": value["attribute"],
             "value": str(value["value"]),
             "type": type(value["value"]).__name__}
            for value in values]


def get_utc_now():
    "Return the UTC epoch (seconds since 1970-01-01)"
    return calendar.timegm(datetime.utcnow().utctimetuple())


class Logger(Device):

    """
    A Tango device whose sole purpose is to wait for someone to tell
    it to send things to Elasticsearch. It works as a standard Tango log
    receiver as well as a specialized (Py)Alarm receiver.

    It tries to make sure that events aren't lost even if Elasticsearch
    temporarily goes away, by buffering.
    """

    __metaclass__ = DeviceMeta

    ElasticsearchHost = device_property(
        dtype=str, default_value="localhost",
        doc="Address of the Elasticsearch host")
    ElasticsearchIndexPrefix = device_property(
        dtype=str, default_value="tango",
        doc="Prefix for the ES index names")
    QueueSize = device_property(
        dtype=int, default_value=10000,
        doc="The maximum number of events to buffer.")
    PushPeriod = device_property(
        dtype=int, default_value=10,
        doc="Number of seconds of sleep between emptying the queue into ES.")

    def init_device(self):

        self.set_state(DevState.INIT)

        self._status = {}  # keep status info for various things
        self._status["n_total_events"] = 0
        self._status["n_logged_events"] = 0
        self._status["thread_restarts"] = 0
        self._status["n_errors"] = 0
        self._status["bad_events"] = 0

        self.get_device_properties()

        # ES setup
        self.es = Elasticsearch(self.ElasticsearchHost)
        self._status["es"] = "Not initialised."
        self._status["es_error"] = None

        # internal queue
        self.queue = Queue(maxsize=self.QueueSize)
        self._status["queue"] = None

        self.existing_indices = set()
        # start periodic push to ES
        if self.PushPeriod > 0:
            self.poll_command("PushQueuedEventsToES",
                              int(self.PushPeriod * 1000))

    def check_es_communication(self):
        "Check that we can still talk to ES properly and update state/status"
        try:
            if not self.es.ping():
                # apparently ES is down so let's just wait;
                # maybe it's just restarting
                if self.get_state() is not DevState.FAULT:
                    self.set_state(DevState.ALARM)
                    self._status["es"] = "Not responding; is it down?"
                if not self.queue.empty():
                    self._status["n_errors"] += 1
                self.error_stream("Elasticsearch did not respond to ping")
                return False
            else:
                self.set_state(PyTango.DevState.ON)
                self._status["es"] = "OK"
                self._status["es_error"] = None
                return True
        except ConnectionError as e:
            # This means we can't establish connection, perhaps not even lookup
            self.set_state(DevState.FAULT)
            self._status["es"] = "Cannot connect; is the address correct?"
            if not self.queue.empty():
                self._status["n_errors"] += 1
                self._status["es_error"] = e
            self.error_stream("Elasticsearch connection error: %r" % e)
            # self.update_status()
            return False
        else:
            self.set_state(PyTango.DevState.ON)
            self._status["es"] = "OK"
            self._status["es_error"] = None
            # self.update_status()
            return True

    def _push_events(self):

        "Check the queue for any arrived events and if any, push them to ES."

        if not self.check_es_communication():
            self.debug_stream(
                "Skipping push; could not talk to ES (~%d events queued)",
                self.queue.qsize())
            return  # no point in trying to send anything

        # Check if there's anything on the queue
        events = []
        while not self.queue.empty():
            events.append(self.queue.get(True))

        if events:
            self._status["n_total_events"] += len(events)
            self._status["queue"] = None
            # check if the indices exist; otherwise we create them
            # with the correct mapping. Is there a better way to do
            # this? Anyway, this should only happen once a day.
            for event in events:
                index = event["_index"]
                if index not in self.existing_indices:
                    self.existing_indices.add(index)
                    if not self.es.indices.exists(index):
                        self.es.indices.create(
                            index, {"mappings": es_mappings[event["_type"]]})
                        self.info_stream("Created new index %s" % index)
            try:
                # send all the events to ES
                inserted, errors = helpers.bulk(self.es, events)
                if errors:
                    self._status["n_errors"] += len(errors)
                    self.error_stream(errors)
                else:
                    self.debug_stream("Pushed %d events to ES" % inserted)
                self._status["n_logged_events"] += inserted
                if self.get_state() is not DevState.ON:
                    self.set_state(DevState.ON)
                    self._status["es_error"] = None
            except Exception as e:
                # There was a problem. Let's put the items back in the queue.
                for event in events:
                    self._queue_item(event)
                self._status["es_error"] = str(e)
                if self.get_state() != DevState.FAULT:
                    self.set_state(DevState.ALARM)
                self.error_stream("Exception while sending data to ES: %s" % e)

    def _get_index(self, group):
        """
        Generate a date based index name for elasticsearch, on the form
        '<prefix>-<group>-YYYY.MM.DD'. This is used by Kibana and should
        also make it easy to prune old data.
        """
        date = time.strftime('%Y.%m.%d', datetime.utcnow().utctimetuple())
        index = "tango-{0}-{1}".format(group, date)
        return index

    def _queue_item(self, item):
        "Try to put an item on the queue"
        try:
            self.queue.put(item, False)
        except Full:
            self._push_events()
            self.warn_stream("Queue full; pushing events")

            self.set_state(DevState.ALARM)
        else:
            self._status["queue"] = ("There are around {0} queued events."
                                     .format(self.queue.qsize()))

    def dev_status(self):
        self.set_status(self._make_status())
        self._status_str = self.get_status()
        return self._status_str

    def update_status(self):
        self.set_status(self._make_status())

    def _make_status(self):
        status = ["Device is in {0} state.".format(self.get_state())]
        status.append("Number of events handled: {n_total_events}"
                      .format(**self._status))
        status.append("Number of events written to database: {n_logged_events}"
                      .format(**self._status))
        status.append("Number of failures to write to database: {n_errors}"
                      .format(**self._status))
        if self._status["queue"]:
            status.append(self._status["queue"])
        if self._status["es"]:
            status.append("Elasticsearch status: {es}".format(**self._status))
        if self._status["es_error"]:
            status.append("Elasticsearch error: {es_error}"
                          .format(**self._status))
        if self._status["bad_events"]:
            status.append("Events that could not be decoded: {0}"
                          .format(**self._status))
        return "\n".join(status)

    @command(dtype_in=[str],
             doc_in="Format: timestamp, level, device, message, ndc, thread")
    def Log(self, event):
        "Send a Tango log event to Elasticsearch"
        self.debug_stream("Log(%r)" % event)
        source = dict(zip(EVENT_MEMBERS, event))
        if not self.queue.full():
            data = {
                "_id": str(uuid4()),  # create a unique document ID
                "_type": "log",
                "_index": self._get_index("logs"),
                "_source": source
            }
            self._queue_item(data)

    @command(dtype_in=str, doc_in="JSON encoded PyAlarm event")
    def Alarm(self, event):
        "Send a PyAlarm event to Elasticsearch"
        self.debug_stream("Alarm(%r)" % event)
        try:
            source = json.loads(event)
        except ValueError as e:
            self.error_stream("Error decoding alarm event: %s", e)
            self.debug_stream(event)
            self._status["bad_events"] += 1
            return

        # we want a @timestamp field for Kibana to work...
        if "timestamp" in source:
            t = source.pop("timestamp")
            source["@timestamp"] = datetime.utcfromtimestamp(t / 1000)

        # make sure there is a priority
        if "priority" not in source:
            sev = str(source["severity"])
            source["priority"] = ALARM_PRIORITIES.get(sev.upper(), 0)

        # slightly hacky way of making things fit the mapping
        source["values"] = stringify_values(source["values"])

        data = {
            "_id": str(uuid4()),  # create a unique document ID
            "_type": "alarm",
            "_index": self._get_index("alarms"),
            "_source": source,
            "_timestamp": source["@timestamp"]
        }
        self._queue_item(data)

    @command(dtype_in=str, doc_in="A message for the fake alarm event")
    def TestAlarm(self, message):
        "Send a test alarm event."
        event = {
            "@timestamp": int(get_utc_now() * 1000),
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

    @command(dtype_in=str, doc_in="A message for the fake log event")
    def TestLog(self, message):
        "Send a test log event."
        event = [str(int(get_utc_now() * 1000)), "DEBUG", "just/testing/1",
                 message, "0", "0"]
        self.Log(event)

    @command
    def PushQueuedEventsToES(self):
        self._push_events()


def main():
    run((Logger,))


if __name__ == "__main__":
    main()
