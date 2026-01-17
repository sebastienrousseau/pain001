=============
Configuration
=============

This guide explains how to configure Pain001 for your specific payment processing needs.

Configuration Methods
=====================

Pain001 can be configured through:

1. **Template Files** - XML template with default settings
2. **Function Parameters** - Direct parameters to `main()`
3. **Environment Variables** - System-level configuration
4. **Configuration Files** - YAML or JSON configuration

XML Template Configuration
==========================

The XML template is the primary configuration method. It defines:

- ISO 20022 version and structure
- Default values for payment information
- Batch settings
- Business rules

**Example Template Structure (pain.001.001.03):**

.. code-block:: xml

    <?xml version="1.0" encoding="UTF-8"?>
    <Document xmlns="urn:iso:std:iso:20022:tech:xsd:pain.001.001.03">
        <CstmrCdtTrfInitn>
            <GrpHdr>
                <MsgId><!-- Generated: Message ID --></MsgId>
                <CreDtTm><!-- Generated: Creation timestamp --></CreDtTm>
                <NbOfTxns><!-- Auto-calculated --></NbOfTxns>
                <CtrlSum><!-- Auto-calculated: Total amount --></CtrlSum>
                <InitgPty>
                    <Nm><!-- From CSV: InitiatingParty --></Nm>
                    <Id>
                        <OrgId>
                            <BICOrBEI><!-- Extracted from IBAN --></BICOrBEI>
                        </OrgId>
                    </Id>
                </InitgPty>
            </GrpHdr>
            <PmtInf>
                <PmtInfId><!-- From CSV: PaymentInformationId --></PmtInfId>
                <PmtMtd>TRF</PmtMtd>
                <BtchBookg><!-- From CSV: BatchBooking (default: false) --></BtchBookg>
                <NbOfTxns><!-- Auto-calculated --></NbOfTxns>
                <CtrlSum><!-- Auto-calculated --></CtrlSum>
                <PmtTpInf>
                    <InstrPrty>NORM</InstrPrty>
                    <SvcLvl>
                        <Cd>SEPA</Cd>
                    </SvcLvl>
                </PmtTpInf>
                <Dbtr>
                    <Nm><!-- From CSV: DebtorName --></Nm>
                    <Id>
                        <OrgId>
                            <Othr>
                                <Id><!-- From CSV: DebtorId --></Id>
                                <SchmeNm>
                                    <Prtry>CUSTOM</Prtry>
                                </SchmeNm>
                            </Othr>
                        </OrgId>
                    </Id>
                </Dbtr>
                <DbtrAcct>
                    <Id>
                        <IBAN><!-- From CSV: DebtorAccountNumber --></IBAN>
                    </Id>
                </DbtrAcct>
                <DbtrAgt>
                    <FinInstnId>
                        <BIC><!-- From CSV: DebtorAgentBIC or extracted from IBAN --></BIC>
                    </FinInstnId>
                </DbtrAgt>
                <CdtTrfTxnInf>
                    <PmtId>
                        <InstrId><!-- From CSV: TransactionId --></InstrId>
                        <EndToEndId><!-- From CSV: EndToEndId --></EndToEndId>
                    </PmtId>
                    <Amt>
                        <InstdAmt Ccy="EUR"><!-- From CSV: Amount --></InstdAmt>
                    </Amt>
                    <CdtrAgt>
                        <FinInstnId>
                            <BIC><!-- From CSV: CreditorAgentBIC --></BIC>
                        </FinInstnId>
                    </CdtrAgt>
                    <Cdtr>
                        <Nm><!-- From CSV: CreditorName --></Nm>
                    </Cdtr>
                    <CdtrAcct>
                        <Id>
                            <IBAN><!-- From CSV: CreditorAccountNumber --></IBAN>
                        </Id>
                    </CdtrAcct>
                    <RmtInf>
                        <Ustrd><!-- From CSV: RemittanceInfo --></Ustrd>
                    </RmtInf>
                </CdtTrfTxnInf>
            </PmtInf>
        </CstmrCdtTrfInitn>
    </Document>

CSV Column Mapping
==================

The following table shows the standard CSV columns for pain.001.001.03:

.. csv-table::
   :header: CSV Column, XML Field, Type, Required, Description, Example

   InitiatingParty, GrpHdr/InitgPty/Nm, String, Yes, Name of initiating party, Company XYZ
   InitiatingPartyId, GrpHdr/InitgPty/Id, String, Yes, ID of initiating party, INITIATOR001
   PaymentInformationId, PmtInf/PmtInfId, String, Yes, Unique payment batch ID, PMT001
   BatchBooking, PmtInf/BtchBookg, Boolean, No, Enable batch booking, "true/false"
   DebtorName, PmtInf/Dbtr/Nm, String, Yes, Name of debtor, Acme Corp
   DebtorId, PmtInf/Dbtr/Id, String, Yes, ID of debtor, DEBTOR001
   DebtorAccountNumber, PmtInf/DbtrAcct/Id/IBAN, String, Yes, IBAN of debtor, DE89370400440532013000
   DebtorAgentBIC, PmtInf/DbtrAgt/BIC, String, No, "BIC of debtors bank", DEUTDEDBBER
   TransactionId, CdtTrfTxnInf/PmtId/InstrId, String, Yes, Unique transaction ID, TXN001
   EndToEndId, CdtTrfTxnInf/PmtId/EndToEndId, String, Yes, End-to-end ID, E2E001
   Amount, CdtTrfTxnInf/Amt/InstdAmt, Decimal, Yes, Payment amount in EUR, 1000.00
   CreditorName, CdtTrfTxnInf/Cdtr/Nm, String, Yes, Name of creditor, Supplier ABC
   CreditorAccountNumber, CdtTrfTxnInf/CdtrAcct/Id/IBAN, String, Yes, IBAN of creditor, DE89370400440532013001
   CreditorAgentBIC, CdtTrfTxnInf/CdtrAgt/BIC, String, No, "BIC of creditors bank", DEUTDEDBBER
   RemittanceInfo, CdtTrfTxnInf/RmtInf/Ustrd, String, No, Payment reference, Invoice #123

ISO 20022 Version-Specific Settings
===================================

Different ISO 20022 versions have different requirements:

**pain.001.001.03 (SEPA v3)**
- Focus: SEPA credit transfers
- Debtor account: Required
- Creditor account: Required
- Currency: EUR only
- Field count: 42

**pain.001.001.06 (Instant Payments)**
- Additional fields for instant payment processing
- Priority levels
- Field count: 44

**pain.001.001.09+ (Modern)**
- Simplified structure
- Enhanced field validation
- Field count: 23

Choose the appropriate version based on your payment network requirements.

Validation Configuration
=========================

Control validation strictness:

.. code-block:: python

    from pain001 import main

    # Strict validation (default)
    main(
        xml_message_type='pain.001.001.03',
        xml_template_file_path='template.xml',
        xsd_schema_file_path='schema.xsd',
        data_file_path='payments.csv'
    )

Validation checks include:

- **Type Validation**: Ensures correct data types (string, number, date)
- **Format Validation**: Checks IBAN/BIC format, email, phone
- **Required Fields**: Verifies all mandatory fields are present
- **Business Rules**: Checks domain-specific rules (e.g., amount > 0)
- **XSD Schema**: Validates against official ISO 20022 schemas

Environment Variables
=====================

Configure Pain001 using environment variables:

.. code-block:: bash

    # Set default message type
    export PAIN001_MESSAGE_TYPE=pain.001.001.03

    # Set default template location
    export PAIN001_TEMPLATE_PATH=/path/to/templates

    # Set XSD schema location
    export PAIN001_XSD_PATH=/path/to/schemas

    # Enable debug logging
    export PAIN001_DEBUG=true

    # Set log level
    export PAIN001_LOG_LEVEL=DEBUG

Accessing from Python:

.. code-block:: python

    import os
    message_type = os.getenv('PAIN001_MESSAGE_TYPE', 'pain.001.001.03')

Performance Tuning
==================

For processing large payment batches:

.. code-block:: python

    from pain001 import main

    # Batch processing with chunking
    import pandas as pd

    df = pd.read_csv('large_payment_file.csv')

    # Process in chunks
    chunk_size = 1000
    for i in range(0, len(df), chunk_size):
        chunk = df.iloc[i:i+chunk_size]
        chunk.to_csv(f'chunk_{i}.csv', index=False)
        main(
            xml_message_type='pain.001.001.03',
            xml_template_file_path='template.xml',
            xsd_schema_file_path='schema.xsd',
            data_file_path=f'chunk_{i}.csv'
        )

Security Configuration
======================

Pain001 implements security best practices:

**XML Security**
- Uses `defusedxml` to prevent XXE attacks
- Validates against schema before processing
- Sanitizes external input

**Database Security**
- Parameterised queries prevent SQL injection
- Input validation for all fields
- No plain text credential storage

**Data Protection**
- Validates all external input
- Secure error messages (no sensitive data in errors)
- Audit logging of all operations

Best Practices
==============

1. **Template Management**
   - Keep templates in version control
   - Use different templates for different versions
   - Document custom template modifications

2. **CSV Preparation**
   - Validate CSV before processing
   - Use consistent encoding (UTF-8)
   - Include headers matching documentation

3. **Error Handling**
   - Catch specific exceptions
   - Log all validation errors
   - Implement retry logic for transient failures

4. **Testing**
   - Test with small datasets first
   - Validate output with your bank
   - Test different ISO 20022 versions separately

5. **Monitoring**
   - Monitor processing times
   - Track success/failure rates
   - Alert on validation failures

Troubleshooting Configuration Issues
====================================

**Issue: "XSD Schema Validation Failed"**

Solution:
- Verify schema file path is correct
- Ensure schema version matches message type
- Check schema file is valid XML

**Issue: "Missing Required Fields"**

Solution:
- Verify CSV has all required columns
- Check column names match documentation
- Ensure no empty cells in required columns

**Issue: "Invalid IBAN Format"**

Solution:
- Validate IBAN format (e.g., DE89370400440532013000)
- Check country code matches IBAN rules
- Use IBAN validator tool to verify

**Issue: "Batch Processing is Slow"**

Solution:
- Process in smaller chunks
- Use parallel processing for independent batches
- Check system resources (CPU, memory)

Next Steps
==========

- Review `Usage Examples <examples.html>`_
- Check the `API Reference <modules.html>`_
- See `FAQ <faq.html>`_ for common questions
