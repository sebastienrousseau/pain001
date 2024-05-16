import os

# Ensure the tests/data directory exists
os.makedirs("tests/data", exist_ok=True)

# Create valid_data.csv
with open("tests/data/valid_data.csv", "w") as f:
    f.write(
        """id,date,nb_of_txs,initiator_name,payment_information_id,payment_method,batch_booking,ctrl_sum,service_level_code,requested_execution_date,debtor_name,debtor_account_IBAN,debtor_agent_BIC,forwarding_agent_BIC,charge_bearer,payment_id,payment_amount,currency,creditor_agent_BIC,creditor_name,creditor_account_IBAN,remittance_information
1,2022-01-01,1,John Doe,12345,TRF,false,100,SEPA,2022-01-01,John Doe,DE89370400440532013000,DEUTDEDBFRA,FORWARD,SHA,12345,100.00,EUR,DABADEHHXXX,Jane Doe,DE89370400440532013001,Invoice 1234
2,2022-01-02,1,Jane Doe,67890,TRF,false,200,SEPA,2022-01-02,Jane Doe,DE89370400440532013001,DEUTDEDBFRA,FORWARD2,SHA,67890,200.00,EUR,DABADEHHXXX,John Doe,DE89370400440532013000,Invoice 5678
"""
    )

# Create empty.csv
with open("tests/data/empty.csv", "w") as f:
    f.write(
        """id,date,nb_of_txs,initiator_name,payment_information_id,payment_method,batch_booking,ctrl_sum,service_level_code,requested_execution_date,debtor_name,debtor_account_IBAN,debtor_agent_BIC,forwarding_agent_BIC,charge_bearer,payment_id,payment_amount,currency,creditor_agent_BIC,creditor_name,creditor_account_IBAN,remittance_information
"""
    )

# Create invalid_data.csv
with open("tests/data/invalid_data.csv", "w") as f:
    f.write(
        """id,date,nb_of_txs,initiator_name,payment_information_id,payment_method,batch_booking,ctrl_sum,service_level_code,requested_execution_date,debtor_name,debtor_account_IBAN,debtor_agent_BIC,forwarding_agent_BIC,charge_bearer,payment_id,payment_amount,currency,creditor_agent_BIC,creditor_name,creditor_account_IBAN,remittance_information
1,2022-01-01,one,John Doe,12345,TRF,false,100,SEPA,2022-01-01,John Doe,DE89370400440532013000,DEUTDEDBFRA,FORWARD,SHA,12345,100.00,EUR,DABADEHHXXX,Jane Doe,DE89370400440532013001,Invoice 1234
2,2022-01-02,1,Jane Doe,67890,TRF,false,two hundred,SEPA,2022-01-02,Jane Doe,DE89370400440532013001,DEUTDEDBFRA,FORWARD2,SHA,67890,200.00,EUR,DABADEHHXXX,John Doe,DE89370400440532013000,Invoice 5678
"""
    )

# Create single_row.csv
with open("tests/data/single_row.csv", "w") as f:
    f.write(
        """id,date,nb_of_txs,initiator_name,payment_information_id,payment_method,batch_booking,ctrl_sum,service_level_code,requested_execution_date,debtor_name,debtor_account_IBAN,debtor_agent_BIC,forwarding_agent_BIC,charge_bearer,payment_id,payment_amount,currency,creditor_agent_BIC,creditor_name,creditor_account_IBAN,remittance_information
1,2022-01-01,1,John Doe,12345,TRF,false,100,SEPA,2022-01-01,John Doe,DE89370400440532013000,DEUTDEDBFRA,FORWARD,SHA,12345,100.00,EUR,DABADEHHXXX,Jane Doe,DE89370400440532013001,Invoice 1234
"""
    )

# Create single_column.csv
with open("tests/data/single_column.csv", "w") as f:
    f.write(
        """id
1
2
3
"""
    )
