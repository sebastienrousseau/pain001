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


import logging
import unittest

from pain001.context.context import Context


class TestContext(unittest.TestCase):
    """Unit tests for the Context class."""

    def setUp(self):
        """Set up the test fixture."""
        Context.instance = None

    def tearDown(self):
        """Tear down the test fixture."""
        if Context.instance:
            Context.instance.logger = None
        Context.instance = None

    def test_singleton(self):
        """Test that Context is a singleton."""
        context1 = Context()
        context2 = Context.get_instance()
        self.assertEqual(context1, context2)
        with self.assertRaises(Exception):
            Context()

    def test_set_name(self):
        """Test that set_name() sets the name of the logger."""
        context = Context.get_instance()
        context.set_name("my_context")
        self.assertEqual(context.name, "my_context")

    def test_set_log_level(self):
        context = Context.get_instance()

        valid_log_levels = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL,
        }

        for level_str, level_int in valid_log_levels.items():
            context.set_log_level(level_str)
            self.assertEqual(context.log_level, level_int)
            context.set_log_level(level_int)
            self.assertEqual(context.log_level, level_int)

        with self.assertRaises(Exception):
            context.set_log_level("INVALID")
        with self.assertRaises(Exception):
            context.set_log_level(12345)  # some invalid int

    def test_init_logger(self):
        context = Context.get_instance()
        context.logger = None
        context.init_logger()
        self.assertIsNotNone(context.logger)

        with self.assertRaises(Exception):
            context.init_logger()

    def test_get_logger(self):
        context = Context.get_instance()
        logger = context.get_logger()
        self.assertIsNotNone(logger)
        self.assertEqual(logger, context.logger)
        context.logger = None
        logger = context.get_logger()
        self.assertIsNotNone(logger)
        self.assertEqual(logger, context.logger)

    def test_log_level_propagation(self):
        context = Context.get_instance()
        context.set_log_level(logging.DEBUG)
        self.assertEqual(context.logger.level, logging.DEBUG)


if __name__ == "__main__":
    unittest.main()
