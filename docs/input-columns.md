# Input columns: the flat vocabulary of the CSV pipeline

The generation pipeline renders a bundled template from flat records:
one row per transaction, the first row also carrying the header and
payment-information columns. This page lists every column the extended
templates understand and the ISO 20022 element each one lands on. It is
generated from the templates themselves by the records twin
(`pain001.twins.column_paths`), so it cannot drift from what the
pipeline does; regenerate it with `scripts/generate_input_columns.py`.

The vocabulary is shared by `pain.001.001.03` and the `.09` to `.13`
editions (0.0.69, the CSV pipeline extension). The `.04` to `.08`
templates keep their earlier, narrower column set.

## Rules

- **Required**: `id`, `date`, `initiator_name`, `payment_id`,
  `debtor_name`, and per row `payment_id`, `payment_amount`,
  `creditor_name` and a currency (`currency` or `payment_currency`).
  One of `requested_execution_date` or `requested_execution_datetime`
  (`.03`: the date only). One of `debtor_account_IBAN` or
  `debtor_account_number`, and one of `debtor_agent_BIC` or
  `debtor_agent_member_id`; the same for the creditor on every row.
- **Optional columns render only when given**; an absent column adds no
  element. `nb_of_txs` and `ctrl_sum` are computed from the rows and
  rendered at both the group-header and payment-information level.
- **Aliases**: `amount` for `payment_amount`, `currency` for
  `payment_currency`, `execution_date` for `requested_execution_date`.
- A scheme name is a code (`SchmeNm/Cd`) when `*_scheme` is given, or a
  proprietary name (`SchmeNm/Prtry`) when `*_scheme_proprietary` is.
  A creditor reference type that is an ISO code (`SCOR`, `RADM`, `RPIN`,
  `FXDR`, `DISP`, `PUOR`) renders as `Cd`, anything else as `Prtry`.
- What the pipeline still cannot carry, per corpus file, is in each
  market file's provenance record under `twins.records.gap`
  ([twins](twins.md)); today that is only the regulatory reporting
  authority block and cheque instructions.

## pain.001.001.09 to .13

| Column | Element(s) |
| :--- | :--- |
| `id` | `CstmrCdtTrfInitn/GrpHdr/MsgId` |
| `date` | `CstmrCdtTrfInitn/GrpHdr/CreDtTm` |
| `nb_of_txs` | `CstmrCdtTrfInitn/GrpHdr/NbOfTxs`; `CstmrCdtTrfInitn/PmtInf/NbOfTxs` |
| `ctrl_sum` | `CstmrCdtTrfInitn/GrpHdr/CtrlSum`; `CstmrCdtTrfInitn/PmtInf/CtrlSum` |
| `initiator_name` | `CstmrCdtTrfInitn/GrpHdr/InitgPty/Nm` |
| `payment_information_id` | `CstmrCdtTrfInitn/PmtInf/PmtInfId` |
| `payment_method` | `CstmrCdtTrfInitn/PmtInf/PmtMtd` |
| `batch_booking` | `CstmrCdtTrfInitn/PmtInf/BtchBookg` |
| `service_level_code` | `CstmrCdtTrfInitn/PmtInf/PmtTpInf/SvcLvl/Cd` |
| `requested_execution_date` | `CstmrCdtTrfInitn/PmtInf/ReqdExctnDt/Dt` |
| `debtor_name` | `CstmrCdtTrfInitn/PmtInf/Dbtr/Nm` |
| `debtor_account_IBAN` | `CstmrCdtTrfInitn/PmtInf/DbtrAcct/Id/IBAN` |
| `debtor_agent_BIC` | `CstmrCdtTrfInitn/PmtInf/DbtrAgt/FinInstnId/BICFI` |
| `charge_bearer` | `CstmrCdtTrfInitn/PmtInf/ChrgBr` |
| `payment_id` | `CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/PmtId/EndToEndId` |
| `payment_amount` | `CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/Amt/InstdAmt` |
| `currency` | `CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/Amt/InstdAmt/@Ccy` |
| `creditor_agent_BIC` | `CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/CdtrAgt/FinInstnId/BICFI` |
| `creditor_name` | `CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/Cdtr/Nm` |
| `creditor_account_IBAN` | `CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/CdtrAcct/Id/IBAN` |
| `remittance_information` | `CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/RmtInf/Ustrd` |
| `instruction_priority` | `CstmrCdtTrfInitn/PmtInf/PmtTpInf/InstrPrty` |
| `local_instrument_code` | `CstmrCdtTrfInitn/PmtInf/PmtTpInf/LclInstrm/Cd` |
| `local_instrument_proprietary` | `CstmrCdtTrfInitn/PmtInf/PmtTpInf/LclInstrm/Prtry` |
| `category_purpose_code` | `CstmrCdtTrfInitn/PmtInf/PmtTpInf/CtgyPurp/Cd` |
| `initiator_street_name` | `CstmrCdtTrfInitn/GrpHdr/InitgPty/PstlAdr/StrtNm` |
| `initiator_building_number` | `CstmrCdtTrfInitn/GrpHdr/InitgPty/PstlAdr/BldgNb` |
| `initiator_postal_code` | `CstmrCdtTrfInitn/GrpHdr/InitgPty/PstlAdr/PstCd` |
| `initiator_town_name` | `CstmrCdtTrfInitn/GrpHdr/InitgPty/PstlAdr/TwnNm` |
| `initiator_country_subdivision` | `CstmrCdtTrfInitn/GrpHdr/InitgPty/PstlAdr/CtrySubDvsn` |
| `initiator_country_code` | `CstmrCdtTrfInitn/GrpHdr/InitgPty/PstlAdr/Ctry` |
| `initiator_address_line` | `CstmrCdtTrfInitn/GrpHdr/InitgPty/PstlAdr/AdrLine` |
| `initiator_lei` | `CstmrCdtTrfInitn/GrpHdr/InitgPty/Id/OrgId/LEI` |
| `initiator_id` | `CstmrCdtTrfInitn/GrpHdr/InitgPty/Id/OrgId/Othr/Id` |
| `initiator_id_scheme` | `CstmrCdtTrfInitn/GrpHdr/InitgPty/Id/OrgId/Othr/SchmeNm/Cd` |
| `debtor_street_name` | `CstmrCdtTrfInitn/PmtInf/Dbtr/PstlAdr/StrtNm` |
| `debtor_building_number` | `CstmrCdtTrfInitn/PmtInf/Dbtr/PstlAdr/BldgNb` |
| `debtor_postal_code` | `CstmrCdtTrfInitn/PmtInf/Dbtr/PstlAdr/PstCd` |
| `debtor_town_name` | `CstmrCdtTrfInitn/PmtInf/Dbtr/PstlAdr/TwnNm` |
| `debtor_country_subdivision` | `CstmrCdtTrfInitn/PmtInf/Dbtr/PstlAdr/CtrySubDvsn` |
| `debtor_country_code` | `CstmrCdtTrfInitn/PmtInf/Dbtr/PstlAdr/Ctry` |
| `debtor_address_line` | `CstmrCdtTrfInitn/PmtInf/Dbtr/PstlAdr/AdrLine` |
| `debtor_lei` | `CstmrCdtTrfInitn/PmtInf/Dbtr/Id/OrgId/LEI` |
| `debtor_id` | `CstmrCdtTrfInitn/PmtInf/Dbtr/Id/OrgId/Othr/Id` |
| `debtor_id_scheme` | `CstmrCdtTrfInitn/PmtInf/Dbtr/Id/OrgId/Othr/SchmeNm/Cd` |
| `debtor_account_number` | `CstmrCdtTrfInitn/PmtInf/DbtrAcct/Id/Othr/Id` |
| `debtor_account_scheme` | `CstmrCdtTrfInitn/PmtInf/DbtrAcct/Id/Othr/SchmeNm/Cd` |
| `debtor_account_currency` | `CstmrCdtTrfInitn/PmtInf/DbtrAcct/Ccy` |
| `debtor_agent_clearing_system` | `CstmrCdtTrfInitn/PmtInf/DbtrAgt/FinInstnId/ClrSysMmbId/ClrSysId/Cd` |
| `debtor_agent_member_id` | `CstmrCdtTrfInitn/PmtInf/DbtrAgt/FinInstnId/ClrSysMmbId/MmbId` |
| `debtor_agent_name` | `CstmrCdtTrfInitn/PmtInf/DbtrAgt/FinInstnId/Nm` |
| `ultimate_debtor_name` | `CstmrCdtTrfInitn/PmtInf/UltmtDbtr/Nm` |
| `instruction_id` | `CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/PmtId/InstrId` |
| `uetr` | `CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/PmtId/UETR` |
| `creditor_street_name` | `CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/Cdtr/PstlAdr/StrtNm` |
| `creditor_building_number` | `CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/Cdtr/PstlAdr/BldgNb` |
| `creditor_postal_code` | `CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/Cdtr/PstlAdr/PstCd` |
| `creditor_town_name` | `CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/Cdtr/PstlAdr/TwnNm` |
| `creditor_country_subdivision` | `CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/Cdtr/PstlAdr/CtrySubDvsn` |
| `creditor_country_code` | `CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/Cdtr/PstlAdr/Ctry` |
| `creditor_address_line` | `CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/Cdtr/PstlAdr/AdrLine` |
| `creditor_account_number` | `CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/CdtrAcct/Id/Othr/Id` |
| `creditor_account_scheme` | `CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/CdtrAcct/Id/Othr/SchmeNm/Cd` |
| `creditor_account_currency` | `CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/CdtrAcct/Ccy` |
| `creditor_agent_clearing_system` | `CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/CdtrAgt/FinInstnId/ClrSysMmbId/ClrSysId/Cd` |
| `creditor_agent_member_id` | `CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/CdtrAgt/FinInstnId/ClrSysMmbId/MmbId` |
| `creditor_agent_name` | `CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/CdtrAgt/FinInstnId/Nm` |
| `ultimate_creditor_name` | `CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/UltmtCdtr/Nm` |
| `purpose_code` | `CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/Purp/Cd` |
| `regulatory_reporting_indicator` | `CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/RgltryRptg/DbtCdtRptgInd` |
| `regulatory_reporting_country` | `CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/RgltryRptg/Dtls/Ctry` |
| `regulatory_reporting_code` | `CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/RgltryRptg/Dtls/Cd` |
| `regulatory_reporting_info` | `CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/RgltryRptg/Dtls/Inf` |
| `creditor_reference` | `CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/RmtInf/Strd/CdtrRefInf/Ref` |
| `creditor_reference_type` | `CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/RmtInf/Strd/CdtrRefInf/Tp/CdOrPrtry/Cd`; `CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/RmtInf/Strd/CdtrRefInf/Tp/CdOrPrtry/Prtry` |
| `creditor_reference_issuer` | `CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/RmtInf/Strd/CdtrRefInf/Tp/Issr` |
| `initiator_id_scheme_proprietary` | `CstmrCdtTrfInitn/GrpHdr/InitgPty/Id/OrgId/Othr/SchmeNm/Prtry` |
| `debtor_id_scheme_proprietary` | `CstmrCdtTrfInitn/PmtInf/Dbtr/Id/OrgId/Othr/SchmeNm/Prtry` |
| `debtor_account_scheme_proprietary` | `CstmrCdtTrfInitn/PmtInf/DbtrAcct/Id/Othr/SchmeNm/Prtry` |
| `creditor_account_scheme_proprietary` | `CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/CdtrAcct/Id/Othr/SchmeNm/Prtry` |
| `debtor_agent_town_name` | `CstmrCdtTrfInitn/PmtInf/DbtrAgt/FinInstnId/PstlAdr/TwnNm` |
| `debtor_agent_country_subdivision` | `CstmrCdtTrfInitn/PmtInf/DbtrAgt/FinInstnId/PstlAdr/CtrySubDvsn` |
| `debtor_agent_country_code` | `CstmrCdtTrfInitn/PmtInf/DbtrAgt/FinInstnId/PstlAdr/Ctry` |
| `creditor_agent_town_name` | `CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/CdtrAgt/FinInstnId/PstlAdr/TwnNm` |
| `creditor_agent_country_subdivision` | `CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/CdtrAgt/FinInstnId/PstlAdr/CtrySubDvsn` |
| `creditor_agent_country_code` | `CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/CdtrAgt/FinInstnId/PstlAdr/Ctry` |
| `additional_remittance_information` | `CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/RmtInf/Strd/AddtlRmtInf` |
| `requested_execution_datetime` | `CstmrCdtTrfInitn/PmtInf/ReqdExctnDt/DtTm` |
| `payment_currency` | `CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/Amt/InstdAmt/@Ccy` |

## pain.001.001.03

The same columns, with these differences: no `uetr`, `initiator_lei`,
`debtor_lei` or `requested_execution_datetime` (the edition has no such
element); `reference_number` and `reference_date` render the referred
document (`RmtInf/Strd/RfrdDocInf`); the instruction id defaults to
`TX-<n>`; `batch_booking` defaults to `false` as it always did.

| Column | Element(s) |
| :--- | :--- |
| `id` | `CstmrCdtTrfInitn/GrpHdr/MsgId` |
| `date` | `CstmrCdtTrfInitn/GrpHdr/CreDtTm` |
| `nb_of_txs` | `CstmrCdtTrfInitn/GrpHdr/NbOfTxs`; `CstmrCdtTrfInitn/PmtInf/NbOfTxs` |
| `ctrl_sum` | `CstmrCdtTrfInitn/GrpHdr/CtrlSum`; `CstmrCdtTrfInitn/PmtInf/CtrlSum` |
| `initiator_name` | `CstmrCdtTrfInitn/GrpHdr/InitgPty/Nm` |
| `payment_information_id` | `CstmrCdtTrfInitn/PmtInf/PmtInfId` |
| `payment_method` | `CstmrCdtTrfInitn/PmtInf/PmtMtd` |
| `batch_booking` | `CstmrCdtTrfInitn/PmtInf/BtchBookg` |
| `service_level_code` | `CstmrCdtTrfInitn/PmtInf/PmtTpInf/SvcLvl/Cd` |
| `requested_execution_date` | `CstmrCdtTrfInitn/PmtInf/ReqdExctnDt` |
| `debtor_name` | `CstmrCdtTrfInitn/PmtInf/Dbtr/Nm` |
| `debtor_account_IBAN` | `CstmrCdtTrfInitn/PmtInf/DbtrAcct/Id/IBAN` |
| `debtor_agent_BIC` | `CstmrCdtTrfInitn/PmtInf/DbtrAgt/FinInstnId/BIC` |
| `charge_bearer` | `CstmrCdtTrfInitn/PmtInf/ChrgBr` |
| `payment_id` | `CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/PmtId/EndToEndId` |
| `payment_amount` | `CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/Amt/InstdAmt` |
| `currency` | `CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/Amt/InstdAmt/@Ccy` |
| `creditor_agent_BIC` | `CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/CdtrAgt/FinInstnId/BIC` |
| `creditor_name` | `CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/Cdtr/Nm` |
| `creditor_account_IBAN` | `CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/CdtrAcct/Id/IBAN` |
| `remittance_information` | `CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/RmtInf/Ustrd` |
| `instruction_priority` | `CstmrCdtTrfInitn/PmtInf/PmtTpInf/InstrPrty` |
| `local_instrument_code` | `CstmrCdtTrfInitn/PmtInf/PmtTpInf/LclInstrm/Cd` |
| `local_instrument_proprietary` | `CstmrCdtTrfInitn/PmtInf/PmtTpInf/LclInstrm/Prtry` |
| `category_purpose_code` | `CstmrCdtTrfInitn/PmtInf/PmtTpInf/CtgyPurp/Cd` |
| `initiator_street_name` | `CstmrCdtTrfInitn/GrpHdr/InitgPty/PstlAdr/StrtNm` |
| `initiator_building_number` | `CstmrCdtTrfInitn/GrpHdr/InitgPty/PstlAdr/BldgNb` |
| `initiator_postal_code` | `CstmrCdtTrfInitn/GrpHdr/InitgPty/PstlAdr/PstCd` |
| `initiator_town_name` | `CstmrCdtTrfInitn/GrpHdr/InitgPty/PstlAdr/TwnNm` |
| `initiator_country_subdivision` | `CstmrCdtTrfInitn/GrpHdr/InitgPty/PstlAdr/CtrySubDvsn` |
| `initiator_country_code` | `CstmrCdtTrfInitn/GrpHdr/InitgPty/PstlAdr/Ctry` |
| `initiator_address_line` | `CstmrCdtTrfInitn/GrpHdr/InitgPty/PstlAdr/AdrLine` |
| `initiator_id` | `CstmrCdtTrfInitn/GrpHdr/InitgPty/Id/OrgId/Othr/Id` |
| `initiator_id_scheme` | `CstmrCdtTrfInitn/GrpHdr/InitgPty/Id/OrgId/Othr/SchmeNm/Cd` |
| `debtor_street_name` | `CstmrCdtTrfInitn/PmtInf/Dbtr/PstlAdr/StrtNm` |
| `debtor_building_number` | `CstmrCdtTrfInitn/PmtInf/Dbtr/PstlAdr/BldgNb` |
| `debtor_postal_code` | `CstmrCdtTrfInitn/PmtInf/Dbtr/PstlAdr/PstCd` |
| `debtor_town_name` | `CstmrCdtTrfInitn/PmtInf/Dbtr/PstlAdr/TwnNm` |
| `debtor_country_subdivision` | `CstmrCdtTrfInitn/PmtInf/Dbtr/PstlAdr/CtrySubDvsn` |
| `debtor_country_code` | `CstmrCdtTrfInitn/PmtInf/Dbtr/PstlAdr/Ctry` |
| `debtor_address_line` | `CstmrCdtTrfInitn/PmtInf/Dbtr/PstlAdr/AdrLine` |
| `debtor_id` | `CstmrCdtTrfInitn/PmtInf/Dbtr/Id/OrgId/Othr/Id` |
| `debtor_id_scheme` | `CstmrCdtTrfInitn/PmtInf/Dbtr/Id/OrgId/Othr/SchmeNm/Cd` |
| `debtor_account_number` | `CstmrCdtTrfInitn/PmtInf/DbtrAcct/Id/Othr/Id` |
| `debtor_account_scheme` | `CstmrCdtTrfInitn/PmtInf/DbtrAcct/Id/Othr/SchmeNm/Cd` |
| `debtor_account_currency` | `CstmrCdtTrfInitn/PmtInf/DbtrAcct/Ccy` |
| `debtor_agent_clearing_system` | `CstmrCdtTrfInitn/PmtInf/DbtrAgt/FinInstnId/ClrSysMmbId/ClrSysId/Cd` |
| `debtor_agent_member_id` | `CstmrCdtTrfInitn/PmtInf/DbtrAgt/FinInstnId/ClrSysMmbId/MmbId` |
| `debtor_agent_name` | `CstmrCdtTrfInitn/PmtInf/DbtrAgt/FinInstnId/Nm` |
| `ultimate_debtor_name` | `CstmrCdtTrfInitn/PmtInf/UltmtDbtr/Nm` |
| `instruction_id` | `CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/PmtId/InstrId` |
| `creditor_street_name` | `CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/Cdtr/PstlAdr/StrtNm` |
| `creditor_building_number` | `CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/Cdtr/PstlAdr/BldgNb` |
| `creditor_postal_code` | `CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/Cdtr/PstlAdr/PstCd` |
| `creditor_town_name` | `CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/Cdtr/PstlAdr/TwnNm` |
| `creditor_country_subdivision` | `CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/Cdtr/PstlAdr/CtrySubDvsn` |
| `creditor_country_code` | `CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/Cdtr/PstlAdr/Ctry` |
| `creditor_address_line` | `CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/Cdtr/PstlAdr/AdrLine` |
| `creditor_account_number` | `CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/CdtrAcct/Id/Othr/Id` |
| `creditor_account_scheme` | `CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/CdtrAcct/Id/Othr/SchmeNm/Cd` |
| `creditor_account_currency` | `CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/CdtrAcct/Ccy` |
| `creditor_agent_clearing_system` | `CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/CdtrAgt/FinInstnId/ClrSysMmbId/ClrSysId/Cd` |
| `creditor_agent_member_id` | `CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/CdtrAgt/FinInstnId/ClrSysMmbId/MmbId` |
| `creditor_agent_name` | `CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/CdtrAgt/FinInstnId/Nm` |
| `ultimate_creditor_name` | `CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/UltmtCdtr/Nm` |
| `purpose_code` | `CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/Purp/Cd` |
| `regulatory_reporting_indicator` | `CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/RgltryRptg/DbtCdtRptgInd` |
| `regulatory_reporting_country` | `CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/RgltryRptg/Dtls/Ctry` |
| `regulatory_reporting_code` | `CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/RgltryRptg/Dtls/Cd` |
| `regulatory_reporting_info` | `CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/RgltryRptg/Dtls/Inf` |
| `creditor_reference` | `CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/RmtInf/Strd/CdtrRefInf/Ref` |
| `creditor_reference_type` | `CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/RmtInf/Strd/CdtrRefInf/Tp/CdOrPrtry/Cd`; `CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/RmtInf/Strd/CdtrRefInf/Tp/CdOrPrtry/Prtry` |
| `creditor_reference_issuer` | `CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/RmtInf/Strd/CdtrRefInf/Tp/Issr` |
| `initiator_id_scheme_proprietary` | `CstmrCdtTrfInitn/GrpHdr/InitgPty/Id/OrgId/Othr/SchmeNm/Prtry` |
| `debtor_id_scheme_proprietary` | `CstmrCdtTrfInitn/PmtInf/Dbtr/Id/OrgId/Othr/SchmeNm/Prtry` |
| `debtor_account_scheme_proprietary` | `CstmrCdtTrfInitn/PmtInf/DbtrAcct/Id/Othr/SchmeNm/Prtry` |
| `creditor_account_scheme_proprietary` | `CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/CdtrAcct/Id/Othr/SchmeNm/Prtry` |
| `debtor_agent_town_name` | `CstmrCdtTrfInitn/PmtInf/DbtrAgt/FinInstnId/PstlAdr/TwnNm` |
| `debtor_agent_country_subdivision` | `CstmrCdtTrfInitn/PmtInf/DbtrAgt/FinInstnId/PstlAdr/CtrySubDvsn` |
| `debtor_agent_country_code` | `CstmrCdtTrfInitn/PmtInf/DbtrAgt/FinInstnId/PstlAdr/Ctry` |
| `creditor_agent_town_name` | `CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/CdtrAgt/FinInstnId/PstlAdr/TwnNm` |
| `creditor_agent_country_subdivision` | `CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/CdtrAgt/FinInstnId/PstlAdr/CtrySubDvsn` |
| `creditor_agent_country_code` | `CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/CdtrAgt/FinInstnId/PstlAdr/Ctry` |
| `additional_remittance_information` | `CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/RmtInf/Strd/AddtlRmtInf` |
| `payment_currency` | `CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/Amt/InstdAmt/@Ccy` |
| `reference_number` | `CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/RmtInf/Strd/RfrdDocInf/Nb` |
| `reference_date` | `CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/RmtInf/Strd/RfrdDocInf/RltdDt` |
| `charge_account_IBAN` | computed or not rendered |
