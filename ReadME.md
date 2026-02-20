# QuickCart Data Integrity — Reconciliation Project

## Project Summary

QuickCart experienced a P0 incident where the Marketing "Total Sales" dashboard did not match the bank settlement statement. This project establishes a single, bank-reconcilable Source of Truth through two workstreams:

**Part A — Python (`clean_transactions.py`):**
Reads raw nested JSON transaction logs (`raw_data.jsonl`), extracts relevant fields, normalizes inconsistent currency formats into a single `amount_usd` float column, filters out test transactions and unrecoverable records, and outputs a clean dataset. Raw logs are also archived to MongoDB as-is for audit purposes.

**Part B — SQL (`reconciliation.sql`):**
Queries the PostgreSQL database to produce three finance-grade outputs:
- Total successful sales (deduplicated across retry attempts)
- Orphan payments (money received with no matching order)
- Discrepancy gap between internal records and bank settlements

---

## Setup Instructions

### Requirements
- Python 3.8+
- PostgreSQL
- MongoDB (local or [MongoDB Atlas](https://www.mongodb.com/atlas) free tier)

Install Python dependencies:
```bash
pip install pymongo psycopg2-binary
```

---

### Step 1: Load Data into PostgreSQL

Create the schema and tables:
```bash
psql "$DATABASE_URL" -f schema.sql
```

Load the seed data creayed from the generator script:

NOTE: if you created a schema; replace your database name in each of these scripts to {schema}.{db_name} to prevent errors 

```bash
psql "$DATABASE_URL" -f quickcart_data/seed_orders.sql
psql "$DATABASE_URL" -f quickcart_data/seed_payments.sql
psql "$DATABASE_URL" -f quickcart_data/seed_bank_settlements.sql
```

Replace `$DATABASE_URL` with your connection string e.g:
```
postgresql://username:password@localhost:5432/quickcart
```

---

### Step 2: Run the Python Cleaning Script

```bash
python clean_transactions.py
```

You will be prompted for:
1. Path to input JSONL file → `quickcart_data/raw_data.jsonl`
2. MongoDB connection string → found in your MongoDB Atlas dashboard under "Connect"
If you're connecting via VSCODE
Replace <db_user> and <db_password> with your created dbuser and password e.g:
```
mongodb+srv://<db_user>:<db_password>@cluster0.wmklndr.mongodb.net/
```
3. Path to output folder → any local folder e.g. `quickcart_data`

This will:
- Archive the raw logs to MongoDB (`quickcart` database, `raw_transactions` collection)
- Output a cleaned file at `<output_folder>/cleaned_data.json`

---

### Step 3: Run the SQL Reconciliation Script

```bash
psql "$DATABASE_URL" -f reconciliation.sql
```

This will print three result sets to the terminal:
1. Total successful sales in dollars
2. List of orphan payments
3. Discrepancy gap between internal totals and bank settlements

---

## Key Design Decisions

- **Earliest successful payment per order is kept** — any subsequent success on the same order is treated as a duplicate retry
- **Replayed transactions are retained** — a replayed event may represent a legitimate distinct attempt and is not excluded at the log level
- **Bank rows with no `payment_id` are excluded from gap calculation** — they cannot be matched to internal records
- **Zero and negative amounts are dropped** — financially meaningless and likely bad data from the source system
- **Raw logs are archived before cleaning** — MongoDB contains the original unmodified records for full auditability


## Summary of Queries 
 - **QUERY 1: Total Successful Sales**
    Uses ROW_NUMBER() to deduplicate multiple payment attempts per order. 
    Only the earliest successful payment per order is counted. 
    Any subsequent success on the same order is treated as a duplicate retry and excluded.
    Amount is converted from cents to dollars by dividing by 100.0 

 - **QUERY 2: Orphan Payments**
   Payments that succeeded but have no associated order.
   These represent money received with no matching order record and must be investigated separately by Finance.

 - **QUERY 3: Discrepancy Gap**
   Compares internal successful sales against bank settled amounts.

   CTEs:
     deduplicated_payments  → one successful payment per order (earliest)
     orphan_payments        → successful payments with no order (for reference)
     deduplicated_settlement → bank rows deduplicated by payment_id to remove
                               duplicate settlement entries from the bank feed
     clean_bank_payments    → excludes bank rows with no payment_id since
                               they cannot be matched to internal records
  
   A LEFT JOIN is used so that internal payments with no matching bank settlement are preserved in the result. 
   These unmatched rows   (NULL bank amount) represent the most critical discrepancies i.e. payments we recorded as successful but the bank never settled.
  
   ***Gap = Internal Total - Bank Total***
   A positive gap means we expected more than the bank settled.

   A negative gap means the bank settled more than we recorded internally.
