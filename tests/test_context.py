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
        """Test that set_log_level() sets the log level of the logger"""
        context = Context.get_instance()

        """Test all valid log levels"""
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

        """
        Test that set_log_level() raises an exception if the log level is
        invalid.
        """
        with self.assertRaises(Exception):
            context.set_log_level("INVALID")
        with self.assertRaises(Exception):
            context.set_log_level(12345)  # some invalid int

    def test_init_logger(self):
        """Test that init_logger() initializes the logger."""
        context = Context.get_instance()

        """Ensure the logger is not initialized"""
        context.logger = None
        context.init_logger()
        self.assertIsNotNone(context.logger)

        """Test that init_logger() raises an exception if called again."""
        with self.assertRaises(Exception):
            context.init_logger()

    def test_get_logger(self):
        """Test that get_logger() returns the logger."""
        context = Context.get_instance()
        logger = context.get_logger()
        self.assertIsNotNone(logger)
        self.assertEqual(logger, context.logger)

        """Test that get_logger() can initialize the logger."""
        context.logger = None
        logger = context.get_logger()
        self.assertIsNotNone(logger)
        self.assertEqual(logger, context.logger)

    def test_log_level_propagation(self):
        """Test that the log level is correctly propagated to the logger."""
        context = Context.get_instance()
        context.set_log_level(logging.DEBUG)
        self.assertEqual(context.logger.level, logging.DEBUG)


if __name__ == "__main__":
    unittest.main()
