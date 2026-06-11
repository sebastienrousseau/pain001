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

import logging
from typing import Optional


class Context:
    """A class that can be used to manage logging.

    Methods:
        __init__(self): Initializes the class and creates a logger.
        get_instance(): Returns the singleton instance of the class.
        get_logger(self): Returns the logger.
        init_logger(self): Initializes the logger.
        set_log_level(self, log_level): Sets the log level of the logger.
        set_name(self, name): Sets the name of the logger.
    """

    instance: Optional["Context"] = None

    @staticmethod
    def get_instance() -> "Context":
        """Returns the singleton instance of the class.

        Returns:
            A Context instance.
        """
        if Context.instance is None:
            Context()
        if Context.instance is None:  # pragma: no cover
            # Defensive check: unreachable because Context() always sets instance
            raise RuntimeError("Failed to initialize Context singleton")
        return Context.instance

    def __init__(self) -> None:
        """Initializes the class and creates a logger.

        Raises:
            RuntimeError: If the class is already initialized.
        """
        if Context.instance is not None:
            raise RuntimeError("This class is a singleton!")
        else:
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

        if self.logger:
            self.logger.setLevel(self.log_level)

    def init_logger(self) -> None:
        """Initializes the logger.

        Raises:
            RuntimeError: If the logger has already been initialized.
        """
        if self.logger is not None:
            raise RuntimeError("Logger has already been initialized")

        self.logger = logging.getLogger(self.name)
        console_handler = logging.StreamHandler()
        self.logger.setLevel(self.log_level)
        log_format = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        console_handler.setFormatter(log_format)
        if not self.logger.handlers:
            self.logger.addHandler(console_handler)
        self.logger.info("Logging initialized")

    def get_logger(self) -> logging.Logger:
        """Returns the logger.

        Returns:
            A Logger instance.
        """
        if self.logger is None:
            self.init_logger()
        return self.logger
