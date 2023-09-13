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

This module contains the create_xml_v5 function which creates the XML tree
for the pain.001.001.05 schema.

"""

import xml.etree.ElementTree as ET
from jinja2 import Environment, FileSystemLoader


def create_xml_v5(root, data):
    """Create the XML tree for the pain.001.001.05 schema.

    Args:
        root (ElementTree.Element): The root element of the XML tree.
        data (list): A list of dictionaries containing the data to be added
        to the XML document.

    Returns:
        The root element of the XML tree.
    """

    # Create CstmrCdtTrfInitn element
    # pylint: disable=E1101
    cstmr_cdt_trf_initn_element = ET.Element("CstmrCdtTrfInitn")
    root.append(cstmr_cdt_trf_initn_element)

    # Create a Jinja2 environment
    env = Environment(loader=FileSystemLoader("."))

    # Load the Jinja2 template
    template = env.get_template("pain.001.001.05.xml")

    # Prepare the data for rendering
    xml_data = {
        "GrpHdr": {
            "MsgId": data[0]["MsgId"],
            "CreDtTm": data[0]["CreDtTm"],
            "NbOfTxs": data[0]["NbOfTxs"],
            "CtrlSum": data[0]["CtrlSum"],
            "InitgPty": data[0]["InitgPty"],
        },
        "PmtInf": [
            {
                "PmtInfId": payment["PmtInfId"],
                "PmtMtd": payment["PmtMtd"],
                "NbOfTxs": payment["NbOfTxs"],
                "CtrlSum": payment["CtrlSum"],
                "PmtTpInf": {"SvcLvl": payment["SvcLvl"]},
                "ReqdExctnDt": payment["ReqdExctnDt"],
                "Dbtr": payment["Dbtr"],
                "DbtrAcct": payment["DbtrAcct"],
                "DbtrAgt": payment["DbtrAgt"],
                "CdtTrfTxInf": [
                    {
                        "PmtId": transaction["PmtId"],
                        "Amt": transaction["Amt"],
                        "CdtrAgt": transaction["CdtrAgt"],
                        "Cdtr": transaction["Cdtr"],
                        "CdtrAcct": transaction["CdtrAcct"],
                    }
                    for transaction in payment["CdtTrfTxInf"]
                ],
            }
            for payment in data[1:]
        ],
    }

    # Render the template
    xml_content = template.render(**xml_data)

    # Parse the rendered XML content and append its children to the root
    rendered_xml_tree = ET.fromstring(xml_content)
    for child in rendered_xml_tree:
        cstmr_cdt_trf_initn_element.append(child)

    return root
