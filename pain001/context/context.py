# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. You may not use this file except in
# compliance with one of those licences. Copies are provided in
# LICENSE-APACHE and LICENSE-MIT.
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the Licences is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied. See the applicable Licence for the specific language
# governing permissions and limitations.

"""Singleton application context that owns the shared pain001 logger."""

import logging
import threading
from typing import Optional


class Context:
    """A singleton that manages the shared pain001 logger.

    Instantiating the class directly raises RuntimeError once the
    singleton exists; use get_instance() instead.

    Lifecycle overview (method details are documented below):

    - ``__init__`` initializes the class and creates a logger.
    - ``get_instance`` returns the singleton instance.
    - ``get_logger`` returns the logger.
    - ``set_log_level`` sets the logger's level.
    - ``set_name`` sets the logger's name.
    """

    instance: Optional["Context"] = None
    _lock: threading.RLock = threading.RLock()

    @staticmethod
    def get_instance() -> "Context":
        """Returns the singleton instance of the class.

        Returns:
            A Context instance.

        Raises:
            RuntimeError: If the singleton failed to initialize
                (defensive check; unreachable in practice).
        """
        if Context.instance is None:
            with Context._lock:
                if Context.instance is None:
                    Context()
        if (
            Context.instance is None
        ):  # pragma: no cover - Context() always sets it
            raise RuntimeError("Failed to initialize Context singleton")
        return Context.instance

    def __init__(self) -> None:
        with Context._lock:
            if Context.instance is not None and Context.instance is not self:
                raise RuntimeError("This class is a singleton!")
            Context.instance = self
            # Never use the root logger ("") — a library must not
            # reconfigure the host application's logging.
            self.name: str = "pain001"
            self.log_level: int = logging.INFO
            self.logger: logging.Logger = logging.getLogger(self.name)
            self.logger.setLevel(self.log_level)
            self.logger.debug("Context initialized")

    def set_name(self, name: str) -> None:
        """Sets the name of the logger.

        Args:
            name: The name of the logger. Empty names are coerced to
                "pain001" so the root logger is never claimed.
        """
        self.name = name or "pain001"

    def set_log_level(self, log_level: int) -> None:
        """Sets the log level of the logger.

        Args:
            log_level: The log level of the logger.

        Raises:
            ValueError: If the log level is invalid.
        """
        valid_log_levels = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL,
        }

        if isinstance(log_level, int):  # Check if log_level is an integer
            if log_level in valid_log_levels.values():
                self.log_level = log_level
            else:
                raise ValueError("Invalid log level")
        else:
            log_level = (
                log_level.strip().upper()
            )  # Strip and convert to uppercase
            if log_level in valid_log_levels:
                self.log_level = valid_log_levels[log_level]
            else:
                raise ValueError("Invalid log level")

        self.logger.setLevel(self.log_level)

    def get_logger(self) -> logging.Logger:
        """Returns the logger.

        Handlers are the caller's business: the package installs only a
        ``NullHandler``, and the command line attaches its own for the
        length of a run (:mod:`pain001.cli._logging`).

        Returns:
            A Logger instance.
        """
        return self.logger
