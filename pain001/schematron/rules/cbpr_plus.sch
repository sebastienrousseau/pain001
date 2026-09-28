<?xml version="1.0" encoding="UTF-8"?>
<!--
  Copyright (C) 2023-2026 Pain001. All rights reserved.
  SPDX-License-Identifier: Apache-2.0 OR MIT
-->
<schema xmlns="http://purl.oclc.org/dsdl/schematron"
        xmlns:sch="http://purl.oclc.org/dsdl/schematron"
        queryBinding="xslt2">
  <title>CBPR+ Cross-Border Payments Schematron Assertions</title>
  <ns prefix="pain" uri="urn:iso:std:iso:20022:tech:xsd:pain.001.001.03"/>
  <pattern id="CBPR-PLUS-CORE">
    <rule context="//pain:CdtTrfTxInf">
      <assert test="string-length(pain:Amt/pain:InstdAmt/@Ccy) = 3" id="CBPR-TX-001">
        Transaction currency must be a valid 3-letter ISO 4217 code.
      </assert>
      <assert test="number(pain:Amt/pain:InstdAmt) &gt; 0" id="CBPR-TX-002">
        Transaction amount must be strictly positive.
      </assert>
      <assert test="boolean(pain:PmtId/pain:EndToEndId) and pain:PmtId/pain:EndToEndId != ''" id="CBPR-TX-003">
        EndToEndId is mandatory for CBPR+ cross-border payments.
      </assert>
      <assert test="not(pain:PmtId/pain:UETR) or string-length(pain:PmtId/pain:UETR) = 36" id="CBPR-TX-004">
        UETR must be a 36-character canonical UUID format when specified.
      </assert>
      <assert test="not(pain:CdtrAgt/pain:FinInstnId/pain:BICFI) or string-length(pain:CdtrAgt/pain:FinInstnId/pain:BICFI) = 8 or string-length(pain:CdtrAgt/pain:FinInstnId/pain:BICFI) = 11" id="CBPR-TX-005">
        Creditor agent BIC must be 8 or 11 characters.
      </assert>
    </rule>
  </pattern>
</schema>
