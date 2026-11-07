========
Glossary
========

.. glossary::

   ABAN
      Agent Bank Account Number - The account number of the debtor's or creditor's bank.

   ACK
      Acknowledgment message confirming receipt of payment instruction.

   API
      Application Programming Interface - Interface for integrating Pain001 with other applications.

   Batch Booking
      Processing where multiple payment transactions are grouped into a single batch for more efficient processing.

   BIC
      Bank Identifier Code - International code identifying a financial institution (e.g., DEUTDEDBBER).

   Bulk Payments
      Processing of multiple payment transactions in a single operation.

   Business Rules
      Domain-specific validation rules beyond simple format validation (e.g., amount > 0).

   Charge Bearer
      Indicates who bears the charges for the payment (debtor, creditor, or shared).

   Creditor
      The party receiving the payment.

   Creditor Agent
      The bank of the creditor processing the incoming payment.

   Creditor Account
      The account number of the creditor (usually an IBAN).

   CSV
      Comma-Separated Values - Text file format for tabular data.

   CstmrCdtTrfInitn
      Customer Credit Transfer Initiation - XML element for pain.001 payment initiation.

   Debtor
      The party initiating and sending the payment.

   Debtor Agent
      The bank of the debtor processing the outgoing payment.

   Debtor Account
      The account number of the debtor (usually an IBAN).

   End-to-End ID
      Unique identifier for a payment used for reconciliation throughout the entire payment chain.

   ESIC
      European Standardized ICT - Standards for electronic payment processing.

   Execution Date
      The date when the payment is actually processed by the bank.

   Group Header
      Container element in pain.001 containing information about the entire payment message.

   GrpHdr
      XML element containing group-level information for pain.001 messages.

   IBAN
      International Bank Account Number - Standardized format for bank account numbers (e.g., DE89370400440532013000).

   Initiation Date
      Date when the payment is initiated/requested.

   Initiating Party
      The entity initiating the payment file/process.

   ISO 20022
      International Organization for Standardization standard for financial communications and transactions.

   ISO 4217
      International Organization for Standardization standard for currency codes (EUR, USD, GBP, etc.).

   Instruction ID
      Unique identifier for a payment instruction (internal tracking).

   Interbank Settlement
      The exchange of payments between banks on behalf of their customers.

   Mandate
      Authorization for recurring payments or standing orders.

   Message ID
      Unique identifier for the entire pain.001 message.

   NAV
      Net Asset Value - Value term sometimes used in payment contexts.

   NOC
      Notification of Change - Message indicating corrections to previous payment information.

   Originating Currency
      The currency of the debtor's account.

   Pain.001
      ISO 20022 standard message type for Customer Credit Transfer Initiation.

   Pain.002
      ISO 20022 standard message type for Customer Payment Status Report, the bank's reply to a pain.001 or pain.008.

   Pain.008
      ISO 20022 standard message type for Customer Direct Debit Initiation.

   Payment Currency
      The currency in which the payment is made.

   Payment Information
      Container for one or more credit transfer transactions from the same debtor.

   Payment Information ID
      Unique identifier for a payment information block (PmtInfId).

   PmtInf
      XML element containing payment information for a group of transactions.

   PmtId
      XML element containing payment identifiers (instruction ID, end-to-end ID).

   PmtTpInf
      Payment Type Information - XML element specifying payment characteristics.

   Purpose Code
      Code indicating the purpose of the payment (e.g., SUPP for supplier payment, SALA for salary).

   Reconciliation
      Matching of payment records between the debtor, banks, and creditor for accounting purposes.

   Remittance Information
      Information about the payment purpose, invoice numbers, or other reference details.

   Return Debit Note
      Message indicating rejection or reversal of a debit transaction.

   Schema Validation
      Verification that XML structure and content conform to XSD specifications.

   SEPA
      Single Euro Payments Area - Regional payment system for efficient euro transfers within European countries.

   Service Level
      Code for the service the payment uses (e.g., ``SEPA`` for a SEPA credit transfer, ``URGP`` for urgent payment, ``NURG`` for non-urgent).

   Settlement
      The actual transfer of funds between debtor and creditor banks.

   SQLite
      Lightweight SQL database system - supports direct data loading by Pain001.

   Structured Remittance
      Remittance information in structured format (e.g., invoice number, due date).

   Submission Timestamp
      Date and time when the payment file is submitted to the bank.

   SWIFT
      Society for Worldwide Interbank Financial Telecommunication - Secure messaging system for bank communications.

   Thematic Processing
      Grouping of transactions based on business rules (e.g., by debtor, creditor, or amount).

   Transaction
      Individual payment within a pain.001 message (credit transfer instruction).

   Transaction ID
      Unique identifier for an individual transaction.

   Transfer Currency
      Currency in which amount is transferred.

   Unstructured Remittance
      Remittance information in free-form text format.

   Validation Rule
      Criterion that data must satisfy (type, format, or business rule).

   Value Date
      Date when the payment amount is credited to the creditor's account.

   XSD
      XML Schema Definition - Format specification language for validating XML documents.

   XSD Schema
      Formal specification file (.xsd) defining valid pain.001 XML structure.

   XXE Attack
      XML External Entity Attack - Security vulnerability in XML processing. Pain001 prevents this with defusedxml.

See Also
========

- `Installation <installation.html>`_
- `Usage Guide <usage.html>`_
- `FAQ <faq.html>`_
- `Configuration <configuration.html>`_

Further Resources
=================

- `ISO 20022 Official Standard <https://www.iso20022.org/>`_
- `SEPA Documentation <https://www.europeanpaymentscouncil.eu/>`_
- `IBAN Registry <https://www.iban.com/>`_
- `BIC Directory <https://www.swift.com/>`_
