<?xml version="1.0" encoding="UTF-8"?>
<!--
  Copyright (C) 2023-2026 Pain001. All rights reserved.
  SPDX-License-Identifier: Apache-2.0 OR MIT
-->
<schema xmlns="http://purl.oclc.org/dsdl/schematron"
        xmlns:sch="http://purl.oclc.org/dsdl/schematron"
        queryBinding="xslt2">
  <title>EPC SEPA Rulebook Schematron Assertions</title>
  <ns prefix="pain" uri="urn:iso:std:iso:20022:tech:xsd:pain.001.001.03"/>
  <pattern id="EPC-SEPA-CORE">
    <rule context="//pain:CdtTrfTxInf">
      <assert test="pain:Amt/pain:InstdAmt/@Ccy = 'EUR'" id="EPC-SCT-001">
        Transaction currency must be EUR for EPC SEPA Credit Transfer.
      </assert>
      <assert test="not(pain:ChrgBr) or pain:ChrgBr = 'SLEV'" id="EPC-SCT-002">
        Charge bearer when specified at transaction level must be SLEV for EPC SEPA payments.
      </assert>
      <assert test="boolean(pain:CdtrAcct/pain:Id/pain:IBAN)" id="EPC-SCT-003">
        Creditor account must be specified as an IBAN.
      </assert>
      <assert test="number(pain:Amt/pain:InstdAmt) &gt; 0" id="EPC-SCT-004">
        Transaction amount must be strictly positive.
      </assert>
      <assert test="number(pain:Amt/pain:InstdAmt) &lt;= 999999999.99" id="EPC-SCT-005">
        Transaction amount must not exceed 999,999,999.99 EUR.
      </assert>
      <assert test="not(pain:CdtrAgt/pain:FinInstnId/pain:BIC) or string-length(pain:CdtrAgt/pain:FinInstnId/pain:BIC) = 8 or string-length(pain:CdtrAgt/pain:FinInstnId/pain:BIC) = 11" id="EPC-SCT-006">
        Creditor agent BIC when present must be 8 or 11 characters.
      </assert>
      <assert test="boolean(pain:PmtId/pain:EndToEndId) and pain:PmtId/pain:EndToEndId != 'NOTPROVIDED'" id="EPC-SCT-007">
        EndToEndId must be provided and cannot be NOTPROVIDED.
      </assert>
      <!--
        A transaction's service level overrides the batch's for that
        transaction. Every one present must be SEPA: SvcLvl repeats from
        .09, and a Prtry code is not SEPA.
      -->
      <assert test="not(pain:PmtTpInf/pain:SvcLvl[not(pain:Cd = 'SEPA')])" id="EPC-SCT-008">
        Service level when specified at transaction level must be SEPA for EPC SEPA payments.
      </assert>
    </rule>
    <rule context="//pain:PmtInf">
      <assert test="boolean(pain:DbtrAcct/pain:Id/pain:IBAN)" id="EPC-PMT-001">
        Debtor account must be specified as an IBAN.
      </assert>
      <!--
        EPC allows the service level and the charge bearer on the batch
        or on every transaction. Each rule holds when the batch says
        SEPA (SLEV), or says nothing and every transaction does; it
        fails when a value is missing from both places. Every service
        level present must be SEPA, since SvcLvl repeats from .09.
      -->
      <assert test="(pain:PmtTpInf/pain:SvcLvl and not(pain:PmtTpInf/pain:SvcLvl[not(pain:Cd = 'SEPA')])) or (not(pain:PmtTpInf/pain:SvcLvl) and pain:CdtTrfTxInf and not(pain:CdtTrfTxInf[not(pain:PmtTpInf/pain:SvcLvl) or pain:PmtTpInf/pain:SvcLvl[not(pain:Cd = 'SEPA')]]))" id="EPC-PMT-002">
        Service level code must be SEPA, on the payment batch or on every transaction.
      </assert>
      <assert test="pain:ChrgBr = 'SLEV' or (not(pain:ChrgBr) and pain:CdtTrfTxInf and not(pain:CdtTrfTxInf[not(pain:ChrgBr = 'SLEV')]))" id="EPC-PMT-003">
        Charge bearer must be SLEV, on the payment batch or on every transaction.
      </assert>
    </rule>
  </pattern>
</schema>
