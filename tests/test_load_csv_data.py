import unittest
from pain001.csv.load_csv_data import load_csv_data

# Test if the CSV data is loaded correctly


class TestLoadCsvData(unittest.TestCase):
    def test_load_valid_csv(self):
        """
        Test the load_csv_data function with a valid CSV file.

        Args:
            self (TestLoadCsvData): The instance of the TestLoadCsvData class.

        Returns:
            None
        """
        file_path = "tests/data/valid_data.csv"
        data = load_csv_data(file_path)
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)

    def test_load_non_existent_csv(self):
        """
        Test the load_csv_data function with a non-existent CSV file path.

        Args:
            self (TestLoadCsvData): The instance of the TestLoadCsvData class.

        Returns:
            None
        """
        file_path = "tests/data/non_existent.csv"
        with self.assertRaises(FileNotFoundError):
            load_csv_data(file_path)

    def test_load_empty_csv(self):
        """
        Test the load_csv_data function with an empty CSV file path.

        Args:
            self (TestLoadCsvData): The instance of the TestLoadCsvData class.

        Returns:
            None
        """
        file_path = "tests/data/empty.csv"
        with self.assertRaises(ValueError):
            load_csv_data(file_path)

    def test_load_csv_with_invalid_data(self):
        """
        Test the load_csv_data function with a CSV file containing
        invalid data.

            Args:
                self (TestLoadCsvData):
                The instance of the TestLoadCsvData class.

            Returns:
                None
        """
        file_path = "tests/data/invalid_data.csv"
        data = load_csv_data(file_path)
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)

    def test_load_single_row_csv(self):
        """
        Test the load_csv_data function with a CSV file containing
        a single row.

        Args:
            self (TestLoadCsvData): The instance of the TestLoadCsvData class.

        Returns:
            None
        """
        file_path = "tests/data/single_row.csv"
        data = load_csv_data(file_path)
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 1)

    def test_load_single_column_csv(self):
        """
        Test the load_csv_data function with a single column CSV file.

        Args:
            self (TestLoadCsvData): The instance of the TestLoadCsvData class.

        Returns:
            None
        """
        file_path = "tests/data/single_column.csv"
        data = load_csv_data(file_path)
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)

    if __name__ == "__main__":
        unittest.main()
