<?xml version="1.0" encoding="UTF-8"?>
<!--
  Copyright (C) 2023-2026 Pain001. All rights reserved.
  SPDX-License-Identifier: Apache-2.0 OR MIT
-->
<schema xmlns="http://purl.oclc.org/dsdl/schematron"
        xmlns:sch="http://purl.oclc.org/dsdl/schematron"
        queryBinding="xslt2">
  <title>FedNow Instant Payments Schematron Assertions</title>
  <ns prefix="pain" uri="urn:iso:std:iso:20022:tech:xsd:pain.001.001.03"/>
  <pattern id="FEDNOW-CORE">
    <rule context="//pain:CdtTrfTxInf">
      <assert test="pain:Amt/pain:InstdAmt/@Ccy = 'USD'" id="FDN-TX-001">
        Transaction currency must be USD for FedNow instant payments.
      </assert>
      <assert test="pain:ChrgBr = 'DEBT' or pain:ChrgBr = 'SHAR'" id="FDN-TX-002">
        Charge bearer must be DEBT or SHAR for FedNow transfers.
      </assert>
      <assert test="number(pain:Amt/pain:InstdAmt) &gt; 0" id="FDN-TX-003">
        Transaction amount must be strictly positive.
      </assert>
      <assert test="number(pain:Amt/pain:InstdAmt) &lt;= 1000000.00" id="FDN-TX-004">
        Transaction amount must not exceed the FedNow ceiling of $1,000,000.00.
      </assert>
      <assert test="boolean(pain:PmtId/pain:EndToEndId)" id="FDN-TX-005">
        End-to-End identification is required for FedNow payments.
      </assert>
    </rule>
    <rule context="//pain:PmtInf">
      <assert test="pain:PmtTpInf/pain:ClrSysPrvdr/pain:Prtry = 'FDN' or pain:PmtTpInf/pain:SvcLvl/pain:Prtry = 'FDN' or not(pain:PmtTpInf/pain:ClrSysPrvdr)" id="FDN-PMT-001">
        Clearing system identifier must designate FDN when specified.
      </assert>
    </rule>
  </pattern>
</schema>
