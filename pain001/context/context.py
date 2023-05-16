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

import logging


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

    instance = None
    name = ''
    log_level = logging.INFO
    logger = None

    @staticmethod
    def get_instance():
        """Returns the singleton instance of the class.

        Returns:
            A Context instance.
        """
        if Context.instance is None:
            Context.instance = Context()
            return Context.instance

    def __init__(self):
        """Initializes the class and creates a logger.

        Raises:
            Exception: If the class is already initialized.
        """
        if Context.instance is not None:
            raise Exception("This class is a singleton!")
        else:
            Context.instance = self
            self.logger = logging.getLogger(self.name)
            self.logger.setLevel(self.log_level)
            self.logger.info("Context initialized")

    def set_name(self, name):
        """Sets the name of the logger.

        Args:
            name: The name of the logger.
        """
        self.name = name

    def set_log_level(self, log_level):
        """Sets the log level of the logger.

        Args:
            log_level: The log level of the logger.

        Raises:
            Exception: If the log level is invalid.
        """
        if log_level is None or log_level.strip() == "":
            self.log_level = logging.INFO
            return

        if log_level.strip().upper() == "DEBUG":
            self.log_level = logging.DEBUG
        elif log_level.strip().upper() == "INFO":
            self.log_level = logging.INFO
        elif log_level.strip().upper() == "WARNING":
            self.log_level = logging.WARNING
        elif log_level.strip().upper() == "ERROR":
            self.log_level = logging.ERROR
        elif log_level.strip().upper() == "CRITICAL":
            self.log_level = logging.CRITICAL
        elif log_level.strip().upper() == "FATAL":
            self.log_level = logging.FATAL
        elif log_level.strip().upper() == "UNKNOWN":
            self.log_level = logging.UNKNOWN
        else:
            raise Exception("Invalid log level")

    def init_logger(self):
        """Initializes the logger.

        Raises:
            Exception: If the logger has already been initialized.
        """
        if self.logger is not None:
            raise Exception("Logger has already been initialized")

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

    def get_logger(self):
        """Returns the logger.

        Returns:
            A Logger instance.
        """
        if self.logger is None:
            self.init_logger()
        return self.logger
