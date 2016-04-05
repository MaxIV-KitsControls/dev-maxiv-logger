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
                    "type": "date"
                },
                "alarm_tag": {
                    "type": "string"
                },
                "description": {
                    "type": "string"
                },
                "device": {
                    "type": "string"
                },
                "formula": {
                    "type": "string"
                },
                "host": {
                    "type": "string"
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
                            "type": "string"
                        },
                        "value": {
                            "type": "string"
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
