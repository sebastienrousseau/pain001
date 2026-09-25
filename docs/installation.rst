.. SPDX-License-Identifier: Apache-2.0 OR MIT

============
Installation
============

Published package
=================

Use a virtual environment and install from PyPI:

.. code-block:: bash

   python -m pip install pain001
   pain001 --version

Python 3.10 or newer is required. Linux CI tests 3.10–3.14. No Conda default
channel package, native binary, or distro-system-Python compatibility is
claimed.

Optional integrations
=====================

Install the extra for the integration you need, for example:

.. code-block:: bash

   python -m pip install 'pain001[api]'
   pain001 serve --host 127.0.0.1 --port 8000

Other extras are declared in pyproject.toml. Development and documentation
dependencies are Poetry groups, not pip extras named dev, docs or all.
The rules and upload extras on feat/v0.0.71 are unreleased: a source guide
does not imply that the published package contains those additions.

Development checkout
====================

.. code-block:: bash

   git clone --branch feat/v0.0.71 https://github.com/sebastienrousseau/pain001.git
   cd pain001
   poetry install --all-extras --with dev,docs
   poetry run make check
   poetry run make type

Use Python 3.12 for development. See :doc:`development` for the native gates
and :doc:`POLICIES` for the minimum-toolchain policy.

Containers
==========

The published core image is ghcr.io/sebastienrousseau/pain001:latest.
It runs as a non-root user and includes the API extra. Bind a writable
directory when generating files; the CLI output flag names a directory.
Development mockbank images are separate synthetic test services, not a
production bank or a core release.

Verification and troubleshooting
================================

.. code-block:: bash

   python -c 'import pain001; print(pain001.__version__)'
   pain001 versions
   pain001 generate --help

For environment mismatches inspect poetry env info in a source checkout.
Install optional dependencies only for the surfaces you use; missing-extra
diagnostics name the required extra.
