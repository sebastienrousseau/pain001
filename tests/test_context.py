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


import logging
import unittest

from pain001.context.context import Context


class TestContext(unittest.TestCase):
    """Unit tests for the Context class."""

    def setUp(self) -> None:
        """Set up the test fixture."""
        Context.instance = None

    def tearDown(self) -> None:
        """Tear down the test fixture."""
        if Context.instance:
            Context.instance.logger = None
        Context.instance = None

    def test_singleton(self) -> None:
        """Test that Context is a singleton."""
        context1 = Context()
        context2 = Context.get_instance()
        self.assertEqual(context1, context2)
        with self.assertRaises(RuntimeError):
            Context()

    def test_set_name(self) -> None:
        """Test that set_name() sets the name of the logger."""
        context = Context.get_instance()
        context.set_name("my_context")
        self.assertEqual(context.name, "my_context")

    def test_set_log_level(self) -> None:
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

        with self.assertRaises(ValueError):
            context.set_log_level("INVALID")
        with self.assertRaises(ValueError):
            context.set_log_level(12345)  # some invalid int

    def test_init_logger(self) -> None:
        context = Context.get_instance()
        context.logger = None
        context.init_logger()
        self.assertIsNotNone(context.logger)

        with self.assertRaises(RuntimeError):
            context.init_logger()

    def test_get_logger(self) -> None:
        context = Context.get_instance()
        logger = context.get_logger()
        self.assertIsNotNone(logger)
        self.assertEqual(logger, context.logger)
        context.logger = None
        logger = context.get_logger()
        self.assertIsNotNone(logger)
        self.assertEqual(logger, context.logger)

    def test_log_level_propagation(self) -> None:
        context = Context.get_instance()
        context.set_log_level(logging.DEBUG)
        self.assertEqual(context.logger.level, logging.DEBUG)

    def test_init_logger_with_existing_handlers(self) -> None:
        """Test init_logger when logger already has handlers."""
        context = Context.get_instance()

        # Manually add a handler to test line 122 (if not self.logger.handlers)
        test_handler = logging.StreamHandler()
        context.logger.addHandler(test_handler)

        # Remove all handlers and re-initialize to test the handler check
        context.logger.handlers.clear()
        context.logger = None
        context.init_logger()

        # Verify logger was initialized
        self.assertIsNotNone(context.logger)
        self.assertGreater(
            len(context.logger.handlers),
            0,
            "Logger should have at least one handler",
        )


if __name__ == "__main__":
    unittest.main()
