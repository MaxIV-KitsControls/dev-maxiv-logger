## Logger ##

The Logger device is a TANGO device whose purpose is to store event data in an Elasticsearch database. It is currently able to handle standard TANGO logging messages and PyAlarm alarm messages.

The device writes data in a way that is compatible with Kibana 3 and 4. By default, the indices created are on the forms "tango-logs-2016.04.05" and "tango-alarms-2016.04.05" respectively. A new index is created per day. The "tango" prefix can be configured (see below).


## Configuration ##

The device reads a few properties:

- *ElasticsearchHost* must contain the hostname of the ES instance/cluster.
- *ElasticsearchIndexPrefix* is optional and may contain a string prefix for all indices created by the device. The default value is "tango".
- *QueueSize* also optional, prescribes how many events can be kept in memory before they start to be discarded. Default is 1000.
- *PushPeriod* controls the period of pushing data to ES. Default is 10 s. Setting this lower makes ES more up to date, but may be less efficient if there is a lot of traffic. On the other hand, syncing too seldom will lead to the queue illing up and the device having to push data synchronously. This may be a performance issue.


## States ##

- ON the device is working normally
- ALARM the device is experiencing some problems; perhaps there are intermittent problems with communication, or it may be that the queue


## TANGO logging ##

The TANGO logging standard is a very simple device API; it requires a "Log" command that takes an array of strings as argument. These strings are:

* a timestamp (millisecond epoch)
* the level (FATAL, WARNING, INFO, DEBUG, etc)
* the name of the originating device
* the actual log message string
* NDC
* thread

(The last two are not well documented and don't seem to be used for anything. They can be given as empty strings.)


## PyAlarm ##

In order to store PyAlarm events, a patch needs to be applied to PyAlarm (TODO: this feature should be in PyAlarm at some point) and PyAlarm needs to be configured with a "LoggerDevice" property containing the name of the Logger device. Once this is set up, all alarm events (alarms, resets, reminders...) should be stored.


## Testing ##

There are some device tests included, that exercise basic functionality.

There are also a couple of commands intended for testing; "TestLog" and "TestAlarm". If everything is working correctly, they should produce events that get stored in ES just like "real" events.
