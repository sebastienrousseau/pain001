# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Rendered by `make demo` (vhs, https://github.com/charmbracelet/vhs) from
# the repository root. It runs the README Quick Start in a throwaway
# directory: write the starter CSV, validate it, generate the XSD-checked
# pain.001.001.03 file and show its header. Nothing reaches the network.
Output .github/demo.gif

Set Shell "bash"
Set FontSize 14
Set Width 1200
Set Height 640
Set Padding 20
Set Theme "Catppuccin Mocha"

Hide
Type `cd "$(mktemp -d /tmp/pain001-demo.XXXX)" && export PS1='$ ' && clear`
Enter
Show

Type "pain001 init pain.001.001.03 -o payments.csv"
Sleep 500ms
Enter
Sleep 4s

Type "pain001 validate -t pain.001.001.03 -d payments.csv"
Sleep 500ms
Enter
Sleep 6s

Type "pain001 generate -t pain.001.001.03 -d payments.csv -o output"
Sleep 500ms
Enter
Sleep 8s

Type "head -n 12 output/pain.001.001.03.xml"
Sleep 500ms
Enter
Sleep 4s
