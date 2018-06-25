# Mappings for ElasticSearch. Not strictly necessary, but makes it easier to work with
# timestamps. Also searches should be more efficient.

es_mappings = {
    "log": {
        "log": {
            "properties": {
                "@timestamp": {
                    "type": "date"
                },
                "level": {
                    "type": "text",
                    "index": "false"
                },
                "device": {
                    "type": "text",
                    "index": "false"
                },
                "message": {
                    "type": "text"
                },
                "ndc": {
                    "type": "text",  # integer?
                    "index": "false"
                },
                "thread": {
                    "type": "text",  # integer?
                    "index": "false"
                }
            }
        }
    },
    "alarm": {
        "alarm": {
            "properties": {
                "@timestamp": {
                    "type": "date"
                },
                "alarm_tag": {
                    "type": "text",
                    "index": "false"
                },
                "description": {
                    "type": "text"
                },
                "device": {
                    "type": "text",
                    "index": "false"
                },
                "formula": {
                    "type": "text",
                    "index": "false"
                },
                "host": {
                    "type": "text",
                    "index": "false"
                },
                "instance": {
                    "index": "false",  # a random uuid4
                    "type": "text"
                },
                "message": {
                    "index": "false",  # this is e.g. ALARM or RESET
                    "type": "text"
                },
                "priority": {
                    "index": "false",
                    "type": "integer"
                },
                "severity": {
                    "index": "false",  # ALARM, WARNING, INFO, ...
                    "type": "text"
                },
                "timestamp": {
                    "type": "date",
                },
                "active_since": {
                    "type": "date"
                },
                "recovered_at": {
                    "type": "date"
                },
                "user_comment": {
                    "type": "text"
                },
                "values": {
                    "properties": {
                        "attribute": {
                            "type": "text",
                            "index": "false"
                        },
                        "value": {
                            "type": "text",
                            "index": "false"
                        },
                        "type": {
                            "index": "false",  # a python data type
                            "type": "text"
                        }
                    }
                }
            }
        }
    }
}
