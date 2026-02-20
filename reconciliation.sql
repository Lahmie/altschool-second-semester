WITH deduplicated_payments AS (

	SELECT *,
	ROW_NUMBER() OVER (PARTITION BY order_id ORDER BY attempted_at ASC) as row_n
	FROM quickcart.payments
	WHERE status = 'SUCCESS'
)

--QUERY 1: Total successful sales

SELECT SUM(amount_cents)/100.0 AS total_successful_sales_dollars
FROM deduplicated_payments
WHERE row_n = 1;



QUERY 2: orphan payments
SELECT * FROM quickcart.payments
WHERE status = 'SUCCESS'
AND order_id IS NULL;


WITH deduplicated_payments AS (

	SELECT *,
	ROW_NUMBER() OVER (PARTITION BY order_id ORDER BY attempted_at ASC) as row_n
	FROM quickcart.payments
	WHERE status = 'SUCCESS'
),

orphan_payments AS (
	SELECT * FROM quickcart.payments
	WHERE status = 'SUCCESS'
	AND order_id IS NULL
),

deduplicated_settlement AS (

	SELECT *,
	ROW_NUMBER() OVER (PARTITION BY payment_id ORDER BY settled_at ASC) as row_n
	FROM quickcart.bank_settlements
	WHERE status = 'SETTLED'
),

clean_bank_payments AS (
    SELECT *
    FROM deduplicated_settlement
    WHERE row_n = 1
    AND payment_id IS NOT NULL
)


SELECT
    SUM(dp.amount_cents)/100.0 AS internal_total_sales_in_dollars,
    SUM(cb.settled_amount_cents)/100.0 AS bank_total_dollars,
    (SUM(dp.amount_cents) - SUM(cb.settled_amount_cents))/100.0 AS gap_dollars
FROM deduplicated_payments dp
LEFT JOIN clean_bank_payments cb ON dp.payment_id = cb.payment_id
WHERE dp.row_n = 1




