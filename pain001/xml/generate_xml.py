# Copyright (C) 2023 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Import the XML libraries
import xml.etree.ElementTree as ET

# Import the functions from the other modules
from .create_xml_element import create_xml_element


def create_common_elements(parent, row, mapping):
    for xml_tag, csv_column in mapping.items():
        if xml_tag in ["PmtInfId", "PmtMtd"]:
            create_xml_element(parent, xml_tag, row[csv_column])


def create_xml_v3(root, data, mapping):
    print("XML v3")

    # Create CstmrCdtTrfInitn element
    cstmr_cdt_trf_initn_element = ET.Element("CstmrCdtTrfInitn")
    root.append(cstmr_cdt_trf_initn_element)

    # Create GrpHdr element and append it to CstmrCdtTrfInitn
    GrpHdr_element = ET.Element("GrpHdr")
    cstmr_cdt_trf_initn_element.append(GrpHdr_element)

    # Add the MsgId, CreDtTm, and NbOfTxs elements to the GrpHdr element
    for xml_tag, csv_column in mapping.items():
        if xml_tag in ["MsgId", "CreDtTm", "NbOfTxs"]:
            create_xml_element(
                GrpHdr_element,
                xml_tag,
                data[0][csv_column]
            )

    # Create new "InitgPty" element in the XML tree using data from the
    # CSV file
    InitgPty_element = ET.Element("InitgPty")
    create_xml_element(
        InitgPty_element, "Nm", data[0]["initiator_name"]
    )
    GrpHdr_element.append(InitgPty_element)

    for row in data:
        # Create new "PmtInf" element in the XML tree using data from
        # the CSV file
        PmtInf_element = ET.Element("PmtInf")
        cstmr_cdt_trf_initn_element.append(PmtInf_element)

        create_common_elements(PmtInf_element, row, mapping)

        # Add the PmtInfId and PmtMtd elements to the PmtInf element
        # for xml_tag, csv_column in mapping.items():
        #     if xml_tag in ["PmtInfId", "PmtMtd"]:
        #         create_xml_element(
        #             PmtInf_element,
        #             xml_tag,
        #             row[csv_column]
        #         )

        # Create new "BtchBookg" element in the XML tree using data
        # from the CSV file
        create_xml_element(
            PmtInf_element,
            "BtchBookg",
            row["batch_booking"].lower()
        )

        # Create new "NbOfTxs" element in the XML tree using data from
        # the CSV file
        create_xml_element(PmtInf_element, "NbOfTxs", row["nb_of_txs"])

        # Create new "CtrlSum" element in the XML tree using data from
        # the CSV file
        create_xml_element(
            PmtInf_element,
            "CtrlSum",
            f"{row['control_sum']}"
        )

        # Create new "PmtTpInf" element in the XML tree using data from
        # the CSV file
        PmtTpInf_element = ET.Element("PmtTpInf")
        child_element = ET.Element("SvcLvl")
        child_element2 = ET.Element("Cd")
        child_element2.text = row["service_level_code"]
        child_element.append(child_element2)
        PmtTpInf_element.append(child_element)
        PmtInf_element.append(PmtTpInf_element)

        # Create new "ReqdExctnDt" element in the XML tree using data
        # from the CSV file
        create_xml_element(
            PmtInf_element,
            "ReqdExctnDt",
            row["requested_execution_date"]
        )

        # Create new "Dbtr" element in the XML tree using data from
        # the CSV file
        Dbtr_element = ET.Element("Dbtr")
        child_element = ET.Element("Nm")
        child_element.text = row["debtor_name"]
        Dbtr_element.append(child_element)
        PmtInf_element.append(Dbtr_element)

        # Create new "DbtrAcct" element in the XML tree using data
        # from the CSV file
        DbtrAcct_element = ET.Element("DbtrAcct")
        child_element = ET.Element("Id")
        child_element2 = ET.Element("IBAN")
        # replace with the appropriate value
        child_element2.text = row["debtor_account_IBAN"]
        child_element.append(child_element2)
        DbtrAcct_element.append(child_element)
        PmtInf_element.append(DbtrAcct_element)

        # Create new "DbtrAgt" element in the XML tree using data
        # from the CSV file
        DbtrAgt_element = ET.Element("DbtrAgt")
        child_element = ET.Element("FinInstnId")
        child_element2 = ET.Element("BIC")
        # replace with the appropriate value
        child_element2.text = row["debtor_agent_BIC"]
        child_element.append(child_element2)
        DbtrAgt_element.append(child_element)
        PmtInf_element.append(DbtrAgt_element)

        # Create new "ChrgBr" element in the XML tree using data
        # from the CSV file
        child_element = ET.Element("ChrgBr")
        # replace with the appropriate value
        child_element.text = row["charge_bearer"]
        PmtInf_element.append(child_element)

        # Create new "CdtTrfTxInf" element in the XML tree using data
        # from the CSV file
        CdtTrfTxInf_element = ET.Element("CdtTrfTxInf")

        # Create new "PmtId" element in the XML tree using data
        # from the CSV file
        PmtId_element = ET.Element("PmtId")
        child_element = ET.Element("EndToEndId")
        child_element.text = row["payment_id"]
        PmtId_element.append(child_element)
        CdtTrfTxInf_element.append(PmtId_element)

        # Create new "Amt" element in the XML tree using data
        # from the CSV file
        Amt_element = ET.Element("Amt")
        child_element = ET.Element("InstdAmt")
        child_element.text = row["payment_amount"]
        child_element.set("Ccy", row["currency"])
        Amt_element.append(child_element)
        CdtTrfTxInf_element.append(Amt_element)

        # Create new "CdtrAgt" element in the XML tree using data
        # from the CSV file
        CdtrAgt_element = ET.Element("CdtrAgt")
        child_element = ET.Element("FinInstnId")
        child_element2 = ET.Element("BIC")
        child_element2.text = row["creditor_agent_BIC"]
        child_element.append(child_element2)
        CdtrAgt_element.append(child_element)
        CdtTrfTxInf_element.append(CdtrAgt_element)

        # Create new "Cdtr" element in the XML tree using data
        # from the CSV file
        Cdtr_element = ET.Element("Cdtr")
        child_element = ET.Element("Nm")
        child_element.text = row["creditor_name"]
        Cdtr_element.append(child_element)
        CdtTrfTxInf_element.append(Cdtr_element)
        
        # Create new "CdtrAcct" element in the XML tree using data
        # from the CSV file
        CdtrAcct_element = ET.Element("CdtrAcct")
        child_element = ET.Element("Id")
        child_element2 = ET.Element("IBAN")
        child_element2.text = row["creditor_agent_BIC"]
        child_element.append(child_element2)
        CdtrAcct_element.append(child_element)
        CdtTrfTxInf_element.append(CdtrAcct_element)

        # Create new "RmtInf" element in the XML tree using data
        # from the CSV file
        RmtInf_element = ET.Element("RmtInf")
        child_element = ET.Element("Ustrd")
        child_element.text = row["remittance_information"]
        RmtInf_element.append(child_element)
        CdtTrfTxInf_element.append(RmtInf_element)

        # Append the new CdtTrfTxInf element to the PmtInf element
        PmtInf_element.append(CdtTrfTxInf_element)

        # Append the new PmtInf element to the CstmrCdtTrfInitn element
        cstmr_cdt_trf_initn_element.append(PmtInf_element)


def create_xml_v9(root, data, mapping):
    print("XML v9")

    # Create CstmrCdtTrfInitn element
    cstmr_cdt_trf_initn_element = ET.Element("CstmrCdtTrfInitn")
    root.append(cstmr_cdt_trf_initn_element)

    # Create GrpHdr element and append it to CstmrCdtTrfInitn
    GrpHdr_element = ET.Element("GrpHdr")
    cstmr_cdt_trf_initn_element.append(GrpHdr_element)

    # Add the MsgId, CreDtTm, and NbOfTxs elements to the GrpHdr element
    for xml_tag, csv_column in mapping.items():
        if xml_tag in ["MsgId", "CreDtTm", "NbOfTxs"]:
            create_xml_element(GrpHdr_element, xml_tag, data[0][csv_column])

    # Create new "InitgPty" element in the XML tree using data from the
    # CSV file
    InitgPty_element = ET.Element("InitgPty")
    create_xml_element(
        InitgPty_element, "Nm", data[0]["initiator_name"]
    )
    GrpHdr_element.append(InitgPty_element)

    for row in data:
        # Create new "PmtInf" element in the XML tree using data from
        # the CSV file
        PmtInf_element = ET.Element("PmtInf")
        cstmr_cdt_trf_initn_element.append(PmtInf_element)

        create_common_elements(PmtInf_element, row, mapping)

        Dbtr_element = ET.Element("ReqdExctnDt")
        child_element = ET.Element("Dt")
        child_element.text = row["requested_execution_date"]
        Dbtr_element.append(child_element)
        PmtInf_element.append(Dbtr_element)

        # Create new "Dbtr" element in the XML tree using data from
        # the CSV file
        Dbtr_element = ET.Element("Dbtr")
        child_element = ET.Element("Nm")
        child_element.text = row["debtor_name"]
        Dbtr_element.append(child_element)
        PmtInf_element.append(Dbtr_element)

        # Create new "DbtrAcct" element in the XML tree using data
        # from the CSV file
        DbtrAcct_element = ET.Element("DbtrAcct")
        child_element = ET.Element("Id")
        child_element2 = ET.Element("IBAN")
        # replace with the appropriate value
        child_element2.text = row["debtor_account_IBAN"]
        child_element.append(child_element2)
        DbtrAcct_element.append(child_element)
        PmtInf_element.append(DbtrAcct_element)

        # Create new "DbtrAgt" element in the XML tree using data
        # from the CSV file
        DbtrAgt_element = ET.Element("DbtrAgt")
        child_element = ET.Element("FinInstnId")
        child_element2 = ET.Element("BICFI")
        # replace with the appropriate value
        child_element2.text = row["debtor_agent_BIC"]
        child_element2.set(
            "xmlns", "urn:iso:std:iso:20022:tech:xsd:pain.001.001.09")
        child_element.append(child_element2)
        DbtrAgt_element.append(child_element)
        PmtInf_element.append(DbtrAgt_element)

        # Create new "ChrgBr" element in the XML tree using data
        # from the CSV file
        child_element = ET.Element("ChrgBr")
        # replace with the appropriate value
        child_element.text = row["charge_bearer"]
        PmtInf_element.append(child_element)

        # Create new "CdtTrfTxInf" element in the XML tree using data
        # from the CSV file
        CdtTrfTxInf_element = ET.Element("CdtTrfTxInf")

        # Create new "PmtId" element in the XML tree using data
        # from the CSV file
        PmtId_element = ET.Element("PmtId")
        child_element = ET.Element("EndToEndId")
        child_element.text = row["payment_id"]
        PmtId_element.append(child_element)
        CdtTrfTxInf_element.append(PmtId_element)

        # Create new "Amt" element in the XML tree using data
        # from the CSV file
        Amt_element = ET.Element("Amt")
        child_element = ET.Element("InstdAmt")
        child_element.text = row["payment_amount"]
        child_element.set("Ccy", row["currency"])
        Amt_element.append(child_element)
        CdtTrfTxInf_element.append(Amt_element)

        # Create new "CdtrAgt" element in the XML tree using data
        # from the CSV file
        CdtrAgt_element = ET.Element("CdtrAgt")
        child_element = ET.Element("FinInstnId")
        child_element2 = ET.Element("BICFI")
        # replace with the appropriate value
        child_element2.text = row["creditor_agent_BIC"]
        child_element2.set(
            "xmlns", "urn:iso:std:iso:20022:tech:xsd:pain.001.001.09")
        child_element.append(child_element2)
        CdtrAgt_element.append(child_element)
        CdtTrfTxInf_element.append(CdtrAgt_element)

        # Create new "Cdtr" element in the XML tree using data
        # from the CSV file
        Cdtr_element = ET.Element("Cdtr")
        child_element = ET.Element("Nm")
        child_element.text = row["creditor_name"]
        Cdtr_element.append(child_element)
        CdtTrfTxInf_element.append(Cdtr_element)

        # Create new "CdtrAcct" element in the XML tree using data
        # from the CSV file
        CdtrAcct_element = ET.Element("CdtrAcct")
        child_element = ET.Element("Id")
        child_element2 = ET.Element("IBAN")
        child_element2.text = row["creditor_agent_BIC"]
        child_element.append(child_element2)
        CdtrAcct_element.append(child_element)
        CdtTrfTxInf_element.append(CdtrAcct_element)

        # Create new "RmtInf" element in the XML tree using data
        # from the CSV file
        RmtInf_element = ET.Element("RmtInf")
        child_element = ET.Element("Ustrd")
        child_element.text = row["remittance_information"]
        RmtInf_element.append(child_element)
        CdtTrfTxInf_element.append(RmtInf_element)

        # Append the new CdtTrfTxInf element to the PmtInf element
        PmtInf_element.append(CdtTrfTxInf_element)

        # Append the new PmtInf element to the CstmrCdtTrfInitn element
        cstmr_cdt_trf_initn_element.append(PmtInf_element)

        # Create new "SplmtryData" elements in the XML tree using data
        # from the CSV file"
        # Create the main elements
        SplmtryData_element = ET.Element("SplmtryData")
        Envlp_element = ET.SubElement(SplmtryData_element, "Envlp")
        child_element = ET.SubElement(Envlp_element, "WC")
        CdtTrfTxInf_element.append(SplmtryData_element)
