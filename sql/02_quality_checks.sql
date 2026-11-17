-- Each row is one rule; n_failing counts the rows that break it (0 = pass).
-- severity 'error': the data is broken, stop the pipeline.
-- severity 'warn':  surprising and worth a look, but the analysis can go on.

-- 1. Completeness ----------------------------------------------------------
SELECT
    1                          AS check_id,
    'completeness'             AS category,
    'raw file has 64,000 rows' AS check_name,
    'error'                    AS severity,
    abs(count(*) - 64000)      AS n_failing
FROM raw_hillstrom

-- reduntant because in the load file we set the NOT NULL constraint, kept for generality
UNION ALL
SELECT 2, 'completeness', 'no missing values in the raw file', 'error', count(*)
FROM raw_hillstrom
WHERE recency IS NULL OR history IS NULL
   OR mens IS NULL OR womens IS NULL OR zip_code IS NULL OR newbie IS NULL
   OR channel IS NULL OR segment IS NULL OR visit IS NULL
   OR conversion IS NULL OR spend IS NULL

-- 2. Integrity between tables ----------------------------------------------
-- (The foreign keys already guarantee the other direction.)
UNION ALL
SELECT 3, 'integrity', 'every customer has a treatment', 'error', count(*)
FROM customers AS c
LEFT JOIN campaign_assignment AS a ON a.customer_id = c.customer_id
WHERE a.customer_id IS NULL

UNION ALL
SELECT 4, 'integrity', 'every customer has an outcome row', 'error', count(*)
FROM customers AS c
LEFT JOIN campaign_outcomes AS o ON o.customer_id = c.customer_id
WHERE o.customer_id IS NULL

-- 3. Reconciliation: the modelled tables say the same as the raw file ------
UNION ALL
SELECT 5, 'reconciliation', 'modelled tables match the raw file row by row', 'error', count(*)
FROM raw_hillstrom AS r
JOIN analysis_base AS b ON b.customer_id = r.rowid + 1
WHERE r.recency <> b.recency
   OR r.history <> b.history
   OR r.mens <> b.mens
   OR r.womens <> b.womens
   OR replace(r.zip_code, 'Surburban', 'Suburban') <> b.zip_code
   OR r.newbie <> b.newbie
   OR r.channel <> b.channel
   OR r.visit <> b.visit
   OR r.conversion <> b.conversion
   OR r.spend <> b.spend

-- Rebuilds the label independently: 'Mens E-Mail' -> 'mens e-mail' -> 'mens_email'
UNION ALL
SELECT 6, 'reconciliation', 'treatment labels match the raw segment labels', 'error', count(*)
FROM raw_hillstrom AS r
JOIN campaign_assignment AS a ON a.customer_id = r.rowid + 1
WHERE replace(lower(r.segment), ' e-mail', '_email') <> a.treatment

-- 4. Business logic ----------------------------------------------------------
UNION ALL
SELECT 7, 'business logic', 'spend > 0 only for customers who converted', 'error', count(*)
FROM campaign_outcomes
WHERE conversion = 0 AND spend > 0

UNION ALL
SELECT 8, 'business logic', 'every conversion has spend > 0', 'error', count(*)
FROM campaign_outcomes
WHERE conversion = 1 AND spend = 0

UNION ALL
SELECT 9, 'business logic', 'every converted also visited', 'warn', count(*)
FROM campaign_outcomes
WHERE conversion = 1 AND visit = 0

UNION ALL
SELECT 10, 'business logic', 'past-year spend is positive', 'error', count(*)
FROM customers
WHERE history <= 0

UNION ALL
SELECT 11, 'business logic', 'every customer bought men''s or women''s items', 'warn', count(*)
FROM customers
WHERE mens = 0 AND womens = 0

ORDER BY check_id;