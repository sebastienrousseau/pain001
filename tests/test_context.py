import logging
import unittest

from pain001.context.context import Context


class TestContext(unittest.TestCase):
    def setUp(self):
        self.context = Context.get_instance()
        self.context.set_name("test_context")

    def tearDown(self):
        self.context.logger = None
        Context.instance = None

    def test_get_instance(self):
        # Test that the first call to get_instance() creates a new instance
        # of the class.
        first_instance = Context.get_instance()
        self.assertIsNotNone(first_instance)

        # Test that subsequent calls to get_instance() return the same
        # instance.
        second_instance = Context.get_instance()
        self.assertEqual(first_instance, second_instance)

    def test_set_name(self):
        # Test that set_name() sets the name of the logger.
        context = self.context
        context.set_name("my_context")
        self.assertEqual(context.name, "my_context")

    def test_set_log_level(self):
        # Test that set_log_level() sets the log level of the logger.
        context = self.context
        context.set_log_level(logging.DEBUG)
        self.assertEqual(context.log_level, logging.DEBUG)

        # Test that set_log_level() raises an exception if the log level is
        # invalid.
        with self.assertRaises(Exception):
            context.set_log_level("INVALID")

    def test_get_logger(self):
        # Test that get_logger() returns the logger.
        context = self.context
        logger = context.get_logger()
        self.assertIsNotNone(logger)
        self.assertEqual(logger, context.logger)


if __name__ == "__main__":
    unittest.main()
