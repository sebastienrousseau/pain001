import xml.etree.ElementTree as std_et

import defusedxml.ElementTree as et

try:
    el = std_et.Element("root")
    s = et.tostring(el)
    print("defusedxml has tostring")
except Exception as e:
    print(f"defusedxml missing tostring: {e}")
