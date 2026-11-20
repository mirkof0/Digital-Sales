-- Customer segments for phase 3: one row per customer with the binned segment columns.
-- Recency and history are split into 3 groups with about the same counts (pd.qcut, q=3):
-- cut points at 3 and 8 months, and at $92 and $255.
-- The labels must match DIMENSIONS in src/digital_sales/segments.py.

SELECT
    customer_id, treatment, visit,
    CASE WHEN recency <= 3 THEN '1-3 months'
         WHEN recency <= 8 THEN '4-8 months'
         ELSE '9-12 months' END                         AS recency_band,
    CASE WHEN history < 92 THEN 'Under $92'
         WHEN history < 255 THEN '$92-254'
         ELSE '$255+' END                               AS history_band,
    CASE WHEN mens = 1 AND womens = 1 THEN 'Both'
         WHEN mens = 1 THEN 'Men''s only'
         ELSE 'Women''s only' END                       AS buyer_type,
    channel,
    CASE WHEN newbie = 1 THEN 'New' ELSE 'Existing' END AS newbie,
    zip_code
FROM analysis_base
