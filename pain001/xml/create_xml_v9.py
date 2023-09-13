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

"""

This module contains the create_xml_v9 function which creates the XML tree
for the pain.001.001.09 schema.

"""

import xml.etree.ElementTree as ET
from jinja2 import Environment, FileSystemLoader


def create_xml_v9(root, data):
    """Create the XML tree for the pain.001.001.09 schema.

    Args:
        root (ElementTree.Element): The root element of the XML tree.
        data (list): A list of dictionaries containing the data to be added
        to the XML document.

    Returns:
        The root element of the XML tree.
    """

    # Create CstmrCdtTrfInitn element
    # pylint: disable=E1101
    cstmr_cdt_trf_initn = ET.Element("CstmrCdtTrfInitn")
    root.append(cstmr_cdt_trf_initn)

    # Create Jinja2 environment and load template
    env = Environment(loader=FileSystemLoader("."))
    template = env.get_template("pain.001.001.09.xml")

    # Prepare the data
    xml_data = {
        "GrpHdr": {
            "MsgId": data[0]["MsgId"],
            "CreDtTm": data[0]["CreDtTm"],
            "NbOfTxs": data[0]["NbOfTxs"],
            "InitgPty": data[0]["InitgPty"],
        },
        "PmtInf": [
            {
                "PmtInfId": payment["PmtInfId"],
                "PmtMtd": payment["PmtMtd"],
                "NbOfTxs": payment["NbOfTxs"],
                "CtrlSum": payment["CtrlSum"],
                "ReqdExctnDt": payment["ReqdExctnDt"],
                "Dbtr": payment["Dbtr"],
                "DbtrAcct": payment["DbtrAcct"],
                "DbtrAgt": payment["DbtrAgt"],
                "CdtTrfTxInf": [
                    {
                        "PmtId": txn["PmtId"],
                        "Amt": txn["Amt"],
                        "CdtrAgt": txn["CdtrAgt"],
                        "Cdtr": txn["Cdtr"],
                        "CdtrAcct": txn["CdtrAcct"],
                    }
                    for txn in payment["CdtTrfTxInf"]
                ],
            }
            for payment in data[1:]
        ],
    }

    # Render template
    xml_content = template.render(**xml_data)

    # Parse XML content and append to root
    rendered_xml = ET.fromstring(xml_content)
    for child in rendered_xml:
        cstmr_cdt_trf_initn.append(child)

    return root
