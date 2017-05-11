"""Contain the tests for the power supply device server."""

from datetime import datetime
import json
import sys
import os

from mock import MagicMock

# Path setup
path = os.path.join(os.path.dirname(__file__), os.pardir)
sys.path.insert(0, os.path.abspath(path))

from PyTango import DevState
from devicetest import DeviceTestCase
from elasticsearch import ConnectionError
from loggerds import device as logger


# Device test case
class LoggerTestCase(DeviceTestCase):
    """Test case for power supply device server."""

    device = logger.Logger
    properties = {
        'ElasticsearchHost': 'test-es-host',
        'QueueSize': 3,
        'PushPeriod': 0  # turn off polling for the tests
    }

    @classmethod
    def mocking(cls):
        """Mock elasticsearch and some other modules"""
        print "mocking"
        cls.Elasticsearch = logger.Elasticsearch = MagicMock()
        cls.es = MagicMock()
        cls.Elasticsearch.return_value = cls.es
        cls.indices = cls.es.indices
        cls.helpers = logger.helpers = MagicMock()
        cls.uuid4 = logger.uuid4 = MagicMock()
        cls.uuid4.return_value = "uuid4"
        cls.time = logger.time = MagicMock()
        cls.time.strftime.return_value = "2016.04.05"

    def test_state(self):
        assert self.device.state() == DevState.INIT

    def test_connects_to_es(self):
        host = self.properties["ElasticsearchHost"]
        self.Elasticsearch.assert_called_with(host)

    def test_alarms_if_es_unpingable(self):
        self.es.ping.return_value = False
        self.device.PushQueuedEventsToES()
        assert self.device.state() == DevState.ALARM

    def test_faults_if_es_unreachable(self):
        self.es.ping.side_effect = ConnectionError
        self.device.PushQueuedEventsToES()
        assert self.device.state() == DevState.FAULT

    def test_checks_if_index_exists(self):
        self.indices.exists.return_value = True
        event = ["12345", "INFO", "my/test/device",
                 "testing, testing", "wat", "123"]
        self.device.Log(event)
        self.device.PushQueuedEventsToES()
        self.indices.exists.assert_called_once_with("tango-logs-2016.04.05")
        self.indices.create.assert_not_called()  # don't create existing indices

    def test_creates_missing_index(self):
        self.indices.exists.return_value = False
        event = ["12345", "INFO", "my/test/device", "testing, testing",
                 "wat", "123"]
        self.device.Log(event)
        self.device.PushQueuedEventsToES()
        self.indices.create.assert_called_once_with(
            "tango-logs-2016.04.05", {"mappings": logger.es_mappings["log"]})

    def test_handles_log_event(self):
        self.indices.exists.return_value = True
        event = ["12345", "INFO", "my/test/device",
                 "testing, testing", "wat", "123"]
        self.device.Log(event)
        self.device.PushQueuedEventsToES()
        expected = {
            "_id": "uuid4",
            "_type": "log",
            "_index": "tango-logs-2016.04.05",
            "_source": dict(zip(logger.EVENT_MEMBERS, event))
        }
        self.helpers.bulk.assert_called_once_with(self.es, [expected])

    def test_handles_alarm_event(self):
        self.indices.exists.return_value = True
        event = {
            "description": "testing, testing",
            "timestamp": 12345.,
            "host": "test-host-1",
            "device": "just/testing/1",
            "message": "TESTING",
            "alarm_tag": "logger_device_test",
            "severity": "DEBUG",
            "instance": "fisk",
            "values": [{"attribute": "some/device/1/attribute",
                        "value": 278.5}],
            "formula": "This is a test"
        }
        self.device.Alarm(json.dumps(event))
        self.device.PushQueuedEventsToES()
        expected = {
            "_id": "uuid4",
            "_type": "alarm",
            "_index": "tango-alarms-2016.04.05",
            "_timestamp": datetime.utcfromtimestamp(12345. / 1000.),
            "_source": {
                "description": "testing, testing",
                "@timestamp": datetime.utcfromtimestamp(12345. / 1000.),
                "host": "test-host-1",
                "device": "just/testing/1",
                "message": "TESTING",
                "alarm_tag": "logger_device_test",
                "severity": "DEBUG",
                "priority": 100,
                "instance": "fisk",
                "values": [{"attribute": "some/device/1/attribute",
                            "value": "278.5", "type": "float"}],
                "formula": "This is a test"
            }
        }
        self.helpers.bulk.assert_called_once_with(self.es, [expected])

    def test_handles_queue_full(self):
        self.indices.exists.return_value = True
        event = {
            "description": "testing, testing",
            "timestamp": 12345.,
            "host": "test-host-1",
            "device": "just/testing/1",
            "message": "TESTING",
            "alarm_tag": "logger_device_test",
            "severity": "DEBUG",
            "instance": "fisk",
            "values": [{"attribute": "some/device/1/attribute",
                        "value": 278.5}],
            "formula": "This is a test"
        }
        expected = {
            "_id": "uuid4",
            "_type": "alarm",
            "_index": "tango-alarms-2016.04.05",
            "_timestamp": datetime.utcfromtimestamp(12345. / 1000.),
            "_source": {
                "description": "testing, testing",
                "@timestamp": datetime.utcfromtimestamp(12345. / 1000.),
                "host": "test-host-1",
                "device": "just/testing/1",
                "message": "TESTING",
                "alarm_tag": "logger_device_test",
                "severity": "DEBUG",
                "priority": 100,
                "instance": "fisk",
                "values": [{"attribute": "some/device/1/attribute",
                            "value": "278.5", "type": "float"}],
                "formula": "This is a test"
            }
        }
        self.device.Alarm(json.dumps(event))
        self.device.Alarm(json.dumps(event))
        self.device.Alarm(json.dumps(event))
        self.device.Alarm(json.dumps(event))
        self.helpers.bulk.assert_called_once_with(self.es, [expected] * 3)
