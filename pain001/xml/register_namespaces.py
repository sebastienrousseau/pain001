# Copyright (C) 2023-2024 Sebastien Rousseau.
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

import xml.etree.ElementTree as et

# Register the namespace prefixes with the ElementTree module so that
# they are automatically added to the XML tags when the XML elements
# are created (XML tags and CSV columns mapping)


def register_namespaces(payment_initiation_message_type):
    """This function registers the namespaces for the payment initiation
    message type.

    Args:
        payment_initiation_message_type (str):
        The payment initiation message type.

    Returns:
        None.
    """

    # Create the namespace for the payment initiation message type.
    namespace = (
        "urn:iso:std:iso:20022:tech:xsd:" + payment_initiation_message_type
    )

    # Register the namespaces.
    et.register_namespace("", namespace)
    et.register_namespace("xsi", "http://www.w3.org/2001/XMLSchema-instance")
