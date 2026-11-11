===================
Structured Logging
===================

Pain001 uses structured logging to provide consistent, machine-parsable log output. Events emitted through ``log_event`` are formatted as JSON once a handler with ``JSONFormatter`` is installed (``pain001.logging_schema.configure_json_logging()`` does this). The ``generate`` and ``validate`` commands attach a stderr handler for the run: plain text by default, ``JSONFormatter`` with ``--log-format json`` or ``PAIN001_LOG_FORMAT=json``; the level is WARNING, DEBUG with ``-v``, or ``PAIN001_LOG_LEVEL``, and ``PAIN001_LOG_FILE`` adds a file. The CLI's own progress output on stdout stays human-readable text.

Overview
========

Structured logging enables:

- **Machine-parsable logs** - JSON format for log aggregation tools
- **Consistent event naming** - Standardized event names across CLI and library
- **Rich context** - Detailed metadata with each log entry
- **PII protection** - Built-in masking for sensitive data
- **Performance tracking** - Duration and timing metrics

Log Format
==========

All log entries follow this JSON structure:

.. code-block:: json

    {
        "timestamp": "2026-01-14T22:06:40Z",
        "level": "INFO",
        "logger": "pain001.core.core",
        "request_id": "req-e5ffe29b",
        "event": "process_start",
        "version": "<version>",
        "message_type": "pain.001.001.03",
        "data_source_type": "csv"
    }

Standard Events
===============

Process Lifecycle Events
-------------------------

**process_start**
    Process initialization

    Fields:
        - ``message_type``: ISO 20022 message type
        - ``data_source_type``: csv | json | jsonl | parquet | sqlite | list | dict | file | unknown

**process_success**
    Successful process completion

    Fields:
        - ``message_type``: ISO 20022 message type
        - ``record_count``: Number of records processed
        - ``duration_ms``: Total processing time in milliseconds

**process_error**
    Process failure

    Fields:
        - ``error_type``: Exception class name
        - ``error_message``: Error description
        - ``message_type``: ISO 20022 message type (if available)

CLI Events
----------

**cli_args_parsed**
    Command line arguments parsed successfully

    Fields:
        - ``message_type``: ISO 20022 message type
        - ``dry_run``: Boolean flag

**cli_dry_run**
    Dry-run validation completed

    Fields:
        - ``message_type``: ISO 20022 message type
        - ``validation_passed``: Boolean result

Validation Events
-----------------

**validation_success**
    Validation passed

    Fields:
        - ``validation_type``: schema | data | business_rules
        - ``message_type``: ISO 20022 message type

**validation_error**
    Validation failed

    Fields:
        - ``validation_type``: schema | data | business_rules
        - ``error_type``: Exception class name
        - ``error_message``: Error description

Data Loading Events
-------------------

**data_load_start**
    Data loading initiated

    Fields:
        - ``data_source_type``: csv | json | jsonl | parquet | sqlite | list | dict | file | unknown

**data_load_success**
    Data loaded successfully

    Fields:
        - ``data_source_type``: csv | json | jsonl | parquet | sqlite | list | dict | file | unknown
        - ``record_count``: Number of records loaded
        - ``duration_ms``: Loading time in milliseconds

**data_load_error**
    Data loading failed

    Fields:
        - ``data_source_type``: csv | json | jsonl | parquet | sqlite | list | dict | file | unknown
        - ``error_type``: Exception class name
        - ``error_message``: Error description

XML Generation Events
---------------------

**xml_generate_start**
    XML generation initiated

    Fields:
        - ``message_type``: ISO 20022 message type
        - ``record_count``: Number of records to process

**xml_generate_success**
    XML generated successfully

    Fields:
        - ``message_type``: ISO 20022 message type
        - ``record_count``: Number of records in XML
        - ``duration_ms``: Generation time in milliseconds

**xml_generate_error**
    XML generation failed

    Fields:
        - ``message_type``: ISO 20022 message type
        - ``error_type``: Exception class name
        - ``error_message``: Error description

XSD Validation Events
---------------------

**xsd_validation_start**
    XSD validation initiated

**xsd_validation_success**
    XSD validation passed

**xsd_validation_error**
    XSD validation failed

    Fields:
        - ``error_type``: Exception class name
        - ``error_message``: Error description

**execution_summary**
    Comprehensive final report logged at process completion

    Fields:
        - ``status``: SUCCESS | FAILED | COMPLETED_WITH_WARNINGS | ABORTED
        - ``execution_mode``: dry_run | production
        - ``total_records_processed``: Total record count
        - ``counts``: Event counts by level (debug, info, warning, error, critical)
        - ``performance``: Start time, end time, total_duration_ms
        - ``validation_metrics``: Schema validation, checksum validation results
        - ``artifacts``: Output file and log file paths

Namespace Events
----------------

**namespace_register**
    XML namespace registration

    Fields:
        - ``message_type``: ISO 20022 message type

Standard Fields
===============

Core Fields
-----------

- ``event``: Event name (always present)
- ``timestamp``: ISO 8601 timestamp (YYYY-MM-DDTHH:MM:SSZ format, always present)
- ``level``: Log level (INFO, ERROR, etc., always present)
- ``logger``: Logger name (always present)
- ``request_id``: Unique request identifier in format "req-<8-hex-chars>" (always present)
- ``version``: Pain001 library version (always present)

Identity Fields
---------------

- ``component``: Component name
- ``module``: Python module name
- ``function``: Function name

Message Fields
--------------

- ``message_type``: ISO 20022 message type (e.g., pain.001.001.03)
- ``iso_version``: ISO version number

File Path Fields
----------------

- ``template_path``: XML template file path
- ``schema_path``: XSD schema file path
- ``data_source_type``: csv | json | jsonl | parquet | sqlite | list | dict | file | unknown

Statistics Fields
-----------------

- ``record_count``: Number of records
- ``transaction_count``: Number of transactions
- ``duration_ms``: Duration in milliseconds
- ``file_size_bytes``: Size in bytes of the data file or generated XML

Error Fields
------------

- ``error_type``: Exception class name
- ``error_message``: Human-readable error description
- ``error_details``: Additional error context

Validation Fields
-----------------

- ``validation_type``: schema | data | business_rules

Using Structured Logging
=========================

Basic Usage
-----------

.. code-block:: python

    from pain001.logging_schema import (
        log_event,
        Events,
        Fields,
    )
    import logging

    logger = logging.getLogger(__name__)

    # Log a simple event
    log_event(
        logger,
        logging.INFO,
        Events.PROCESS_START,
        message_type="pain.001.001.03",
    )

Process Lifecycle
-----------------

.. code-block:: python

    from pain001.logging_schema import (
        log_process_start,
        log_process_success,
        log_process_error,
    )

    # Start process
    start_time = log_process_start(
        logger,
        "pain.001.001.03",
        "csv",
    )

    try:
        # ... process data ...
        
        # Log success
        log_process_success(
            logger,
            start_time,
            "pain.001.001.03",
            record_count=100,
        )
    except Exception as e:
        # Log error
        log_process_error(
            logger,
            e,
            "pain.001.001.03",
        )
        raise

Validation Logging
------------------

.. code-block:: python

    from pain001.logging_schema import log_validation_event

    try:
        # Perform validation
        validate_schema(data)
        
        # Log success
        log_validation_event(
            logger,
            "schema",
            True,
            message_type="pain.001.001.03",
        )
    except ValidationError as e:
        # Log error
        log_validation_event(
            logger,
            "schema",
            False,
            e,
            message_type="pain.001.001.03",
        )
        raise

PII Protection
==============

Pain001 includes built-in PII masking for sensitive financial data:

.. code-block:: python

    from pain001.logging_schema import mask_sensitive_data

    # Mask IBAN (show first 4 and last 4 characters)
    iban = "GB29NWBK60161331926819"
    masked = mask_sensitive_data(iban, 4)
    # Result: "GB29**************6819"

    # Log with masked data
    log_event(
        logger,
        logging.INFO,
        Events.DATA_LOAD_SUCCESS,
        account=mask_sensitive_data(iban),
    )

**Sensitive Data Guidelines:**

- **IBAN**: Show first 4 + last 4 characters
- **BIC**: Show first 4 + last 2 characters
- **Names**: Use ``<REDACTED>`` for Debtor/Creditor names in INFO logs
- **Amounts**: Use ``<REDACTED>`` in INFO logs
- **Full data**: Only log at DEBUG level with explicit consent

Log Aggregation
===============

Parsing JSON Logs
-----------------

.. code-block:: python

    import json

    # Parse log line
    with open('app.log') as f:
        for line in f:
            entry = json.loads(line)
            if entry['event'] == 'process_error':
                print(f"Error: {entry['error_message']}")

Elasticsearch Integration
-------------------------

JSON logs can be directly ingested into Elasticsearch:

.. code-block:: python

    import logging
    from pythonjsonlogger import jsonlogger

    # Configure JSON logger
    logger = logging.getLogger()
    handler = logging.StreamHandler()
    formatter = jsonlogger.JsonFormatter()
    handler.setFormatter(formatter)
    logger.addHandler(handler)

Splunk Integration
------------------

Forward logs to Splunk with structured fields:

.. code-block:: bash

    # Configure Splunk Universal Forwarder
    [monitor:///var/log/pain001/*.log]
    sourcetype = json
    index = payments

CloudWatch Logs
---------------

.. code-block:: python

    import watchtower
    import logging

    logger = logging.getLogger()
    logger.addHandler(watchtower.CloudWatchLogHandler())

Performance Monitoring
======================

All process events include timing information:

.. code-block:: json

    {
        "event": "process_success",
        "message_type": "pain.001.001.03",
        "record_count": 1000,
        "duration_ms": 450,
        "generation_ms": 320
    }

Use these fields to:

- Track processing performance
- Identify bottlenecks
- Set SLO alerts
- Monitor system health

Example Queries
---------------

**Find slow processes:**

.. code-block:: python

    # Filter logs where duration > 5 seconds
    slow_processes = [
        entry for entry in logs
        if entry.get('duration_ms', 0) > 5000
    ]

**Count errors by type:**

.. code-block:: python

    from collections import Counter
    
    errors = [
        entry['error_type']
        for entry in logs
        if entry.get('event') == 'process_error'
    ]
    
    error_counts = Counter(errors)

Best Practices
==============

1. **Always use structured logging** for programmatic access
2. **Include message_type** in all payment-related events
3. **Mask sensitive data** (IBAN, BIC, names, amounts)
4. **Log durations** for performance monitoring
5. **Use consistent event names** from the Events class
6. **Include error context** for debugging
7. **Log at appropriate levels** (DEBUG for details, INFO for lifecycle, ERROR for failures)
8. **Track requests** using request_id for distributed tracing
9. **Monitor execution summaries** for at-a-glance health status

Request Tracing (v0.0.46+)
===========================

Every log entry includes a unique ``request_id`` for end-to-end request tracking:

.. code-block:: python

    from pain001.logging_schema import set_request_id, get_request_id

    # Set custom request ID (optional - auto-generated if not set)
    set_request_id("req-custom01")

    # Get current request ID
    request_id = get_request_id()  # Returns "req-custom01" or auto-generated ID

    # All log_event calls automatically include request_id
    log_event(
        logger,
        logging.INFO,
        Events.PROCESS_START,
        message_type="pain.001.001.03"
    )
    # Output includes: "request_id": "req-custom01"

**Request ID Format:** ``req-<8-hex-chars>`` (e.g., ``req-e5ffe29b``)

**Use Cases:**
- Correlate logs across distributed systems
- Track payment processing from API to file generation
- Debug issues across microservices
- Aggregate logs by transaction

Execution Summary Reports (v0.0.46+)
=====================================

Automatically log comprehensive summary at process completion:

.. code-block:: python

    from pain001.logging_schema import ExecutionSummaryTracker

    # Use as context manager (automatic tracking)
    with ExecutionSummaryTracker(
        logger=logger,
        message_type="pain.001.001.03",
        dry_run=False
    ) as tracker:
        # Process payments
        tracker.increment_processed_records(1250)
        
        # Track validation results
        tracker.set_validation_result("schema_validation", "PASSED")
        tracker.set_validation_result("checksum_validation", "PASSED")
        
        # Set output paths
        tracker.output_file = "/path/to/output.xml"
        tracker.log_file = "/path/to/logfile.log"
        
    # Automatic summary logged on exit

**Example Summary Output:**

.. code-block:: json

    {
        "timestamp": "2026-01-14T22:06:40Z",
        "level": "INFO",
        "logger": "pain001.core.core",
        "request_id": "req-e5ffe29b",
        "event": "execution_summary",
        "version": "<version>",
        "message": "Execution Summary Report",
        "summary": {
            "status": "SUCCESS",
            "execution_mode": "production",
            "total_records_processed": 1250,
            "counts": {
                "debug": 5,
                "info": 12,
                "warning": 0,
                "error": 0,
                "critical": 0
            },
            "performance": {
                "start_time": "2026-01-14T22:06:38Z",
                "end_time": "2026-01-14T22:06:40Z",
                "total_duration_ms": 2105
            },
            "validation_metrics": {
                "schema_validation": "PASSED",
                "checksum_validation": "PASSED"
            },
            "artifacts": {
                "output_file": "/path/to/output.xml",
                "log_file": "/path/to/logfile.log"
            }
        }
    }

**Status Values:**
- ``SUCCESS``: All operations completed without errors or warnings
- ``COMPLETED_WITH_WARNINGS``: Completed but with non-critical warnings
- ``FAILED``: Errors encountered during execution
- ``ABORTED``: Process terminated early

**Integration Benefits:**
- Dashboard indicators (green/yellow/red status)
- Reconciliation via total_records_processed
- Performance regression tracking (duration_ms)
- Automated health monitoring
- Management-friendly at-a-glance reports

Next Steps
==========

- Review `Usage Guide <usage.html>`_ for integration examples
- Check `Examples <examples.html>`_ for real-world patterns
- See `API Reference <modules.html>`_ for detailed function signatures
