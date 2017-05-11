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
                    "type": "string",
                    "index": "not_analyzed"
                },
                "device": {
                    "type": "string",
                    "index": "not_analyzed"
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
                    "type": "date"
                },
                "alarm_tag": {
                    "type": "string",
                    "index": "not_analyzed"
                },
                "description": {
                    "type": "string"
                },
                "device": {
                    "type": "string",
                    "index": "not_analyzed"
                },
                "formula": {
                    "type": "string",
                    "index": "not_analyzed"
                },
                "host": {
                    "type": "string",
                    "index": "not_analyzed"
                },
                "instance": {
                    "index": "not_analyzed",  # a random uuid4
                    "type": "string"
                },
                "message": {
                    "index": "not_analyzed",  # this is e.g. ALARM or RESET
                    "type": "string"
                },
                "priority": {
                    "index": "not_analyzed",
                    "type": "integer"
                },
                "severity": {
                    "index": "not_analyzed",  # ALARM, WARNING, INFO, ...
                    "type": "string"
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
                    "type": "string"
                },
                "values": {
                    "properties": {
                        "attribute": {
                            "type": "string",
                            "index": "not_analyzed"
                        },
                        "value": {
                            "type": "string",
                            "index": "not_analyzed"
                        },
                        "type": {
                            "index": "not_analyzed",  # a python data type
                            "type": "string"
                        }
                    }
                }
            }
        }
    }
}
