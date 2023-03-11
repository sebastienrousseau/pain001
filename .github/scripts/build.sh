#!/usr/bin/env bash

# Exit when any command fails.
set -e

PYTHON_VERSION=${PYTHON_VERSION:-3.9}

pip install -U -r .github/scripts/requirements.txt
python setup.py develop
# python -m pytest # Run the tests without IPython.
pip install ipython
# python -m pytest # Now run the tests with IPython.
pylint pain001 --ignore=test_components_py3.py,parser_fuzz_test.py,console
if [[ ${PYTHON_VERSION} == 3.9 ]]; then
    # Run type-checking.
    pip install pytype
    # pytype -x pain001/test_components_py3.py
fi
