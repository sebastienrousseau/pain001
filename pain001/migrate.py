# Copyright (C) 2023-2026 Sebastien Rousseau.
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

"""CLI for ISO 20022 version migration."""

import click

from pain001.migration import VersionMapper


@click.command()
@click.option("--from", "from_version", required=True, help="Source version, e.g. v03")
@click.option("--to", "to_version", required=True, help="Target version, e.g. v09")
@click.option("--source", "source_path", required=True, type=click.Path(exists=True, dir_okay=False, readable=True))
@click.option("--output", "output_path", type=click.Path(dir_okay=False, writable=True))
def main(
    from_version: str,
    to_version: str,
    source_path: str,
    output_path: str | None,
) -> None:
    """Migrate payment data between supported ISO 20022 versions."""
    mapper = VersionMapper()
    migrated_rows = mapper.migrate_file(source_path, from_version, to_version)
    mapper.validate_migrated_rows(migrated_rows, to_version)

    destination = output_path or mapper.default_output_path(source_path, to_version)
    mapper.write_csv(migrated_rows, destination)
    click.echo(destination)


if __name__ == "__main__":
    main()

