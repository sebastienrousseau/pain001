<?xml version="1.0" encoding="UTF-8"?>
<!--
  SPDX-License-Identifier: Apache-2.0 OR MIT

  Template private bank profile, document-level rules (ISO Schematron).
  "Example Bank" is fictional. Each assertion is one constraint a usage
  guideline adds to the ISO schema; give each a stable id. The prefix is
  bound to pain.001.001.09 and is rebound to the version of the
  document checked, within the pain.001 family.
-->
<schema xmlns="http://purl.oclc.org/dsdl/schematron"
        queryBinding="xslt2">
  <title>Example Bank pain.001 profile (template)</title>
  <ns prefix="pain" uri="urn:iso:std:iso:20022:tech:xsd:pain.001.001.09"/>
  <pattern id="EXB-GROUP">
    <rule context="//pain:GrpHdr">
      <assert test="string-length(pain:InitgPty/pain:Nm) &lt;= 35" id="EXB-INITG-NAME">
        Example Bank truncates the initiating party name after 35 characters.
      </assert>
    </rule>
  </pattern>
  <pattern id="EXB-PAYMENT">
    <rule context="//pain:PmtInf">
      <assert test="boolean(pain:PmtTpInf/pain:SvcLvl/pain:Cd)" id="EXB-SVCLVL">
        Example Bank requires a service level code on every payment block.
      </assert>
    </rule>
  </pattern>
</schema>
