import datetime


def validate_csv_data(data):
    """Validate the CSV data before processing it.

    Args:
        data (list): A list of dictionaries containing the CSV data.

    Returns:
        bool: True if the data is valid, False otherwise.
    """
    required_columns = {
        "id": int,
        "date": datetime.datetime,
        "nb_of_txs": int,
        "ctrl_sum": float,
        "initiator_name": str,
        "payment_information_id": str,
        "payment_method": str,
        "batch_booking": bool,
        "service_level_code": str,
        "requested_execution_date": datetime.datetime,
        "debtor_name": str,
        "debtor_account_IBAN": str,
        "debtor_agent_BIC": str,
        "forwarding_agent_BIC": str,
        "charge_bearer": str,
        "payment_id": str,
        "payment_amount": float,
        "currency": str,
        "creditor_agent_BIC": str,
        "creditor_name": str,
        "creditor_account_IBAN": str,
        "remittance_information": str,
    }

    if not data:
        print("Error: The CSV data is empty.")
        return False

    is_valid = True

    for row in data:
        missing_columns = []
        invalid_columns = []
        for column, data_type in required_columns.items():
            value = row.get(column)
            if value is None or value.strip() == "":
                missing_columns.append(column)
                is_valid = False
            else:
                try:
                    if data_type == int:
                        int(value)
                    elif data_type == float:
                        float(value)
                    elif data_type == bool:
                        if value.strip().lower() not in [
                            "true",
                            "false",
                        ]:
                            raise ValueError
                    elif data_type == datetime.datetime:
                        try:
                            if value.endswith("Z"):
                                value = value[:-1] + "+00:00"
                            datetime.datetime.fromisoformat(value)
                        except ValueError:
                            datetime.datetime.strptime(
                                value, "%Y-%m-%d"
                            )
                    else:
                        str(value)
                except ValueError:
                    invalid_columns.append(column)
                    is_valid = False
        if missing_columns:
            print(
                f"Error: Missing value(s) for column(s) {missing_columns} "
                f"in row: {row}"
            )
        if invalid_columns:
            expected_types = [
                required_columns[col].__name__
                for col in invalid_columns
            ]
            print(
                f"Error: Invalid data type for column(s) {invalid_columns}, "
                f"expected {expected_types} in row: {row}"
            )

    return is_valid
