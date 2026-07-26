#!/usr/bin/env python3
"""Atheris fuzz harness for Pain001's input-validation surface.

Fuzzes the three validators that face raw, attacker-controllable input
before any XML exists: IBAN validation (format + mod-97 checksum), BIC
structure validation, and ISO 20022 charset sanitisation. The contract
under test: these functions must never raise on arbitrary text — they
return verdicts, and any uncaught exception is a finding.

Run locally:

    pip install atheris
    python fuzz/fuzz_validation.py -atheris_runs=100000

Corpus-free by design; atheris' coverage guidance finds the interesting
inputs (mixed-script strings, checksum boundary values, embedded NULs).
"""

import sys

import atheris

with atheris.instrument_imports():
    from pain001.validation.bic_validator import validate_bic_format
    from pain001.validation.charset import sanitize_to_charset
    from pain001.validation.iban_validator import (
        validate_iban,
        validate_iban_checksum,
        validate_iban_safe,
    )


def test_one_input(data: bytes) -> None:
    fdp = atheris.FuzzedDataProvider(data)
    text = fdp.ConsumeUnicodeNoSurrogates(256)

    # Verdict-returning APIs must never raise on arbitrary input.
    validate_iban_safe(text)
    validate_iban_checksum(text)
    validate_iban(text, strict=False)
    validate_bic_format(text)

    # Sanitisation must be total and idempotent.
    cleaned = sanitize_to_charset(text)
    if sanitize_to_charset(cleaned) != cleaned:
        raise AssertionError(
            "sanitize_to_charset is not idempotent for: %r" % text
        )


def main() -> None:
    atheris.Setup(sys.argv, test_one_input)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
