-- 1. Raw layer: the file as downloaded. Types are set, values untouched.

CREATE TABLE raw_hillstrom AS
SELECT * 
FROM read_csv(
    '__RAW_CSV__',
    header = true,
    types = {
        'recency':         'INTEGER',
        'history':         'DECIMAL(10,2)',
        'mens':            'INTEGER',
        'womens':          'INTEGER',
        'zip_code':        'VARCHAR',
        'newbie':          'INTEGER',
        'channel':         'VARCHAR',
        'segment':         'VARCHAR',
        'visit':           'INTEGER',
        'conversion':      'INTEGER',
        'spend':           'DECIMAL(10,2)'
    }
);

-- 2. Modelled layer: three tables
-- Who the customer was BEFORE the campaign (model features only).
CREATE TABLE customers (
    customer_id     INTEGER PRIMARY KEY,
    recency         INTEGER       NOT NULL CHECK (recency BETWEEN 1 AND 12),
    history         DECIMAL(10,2) NOT NULL CHECK (history >= 0),
    mens            INTEGER       NOT NULL CHECK (mens IN (0, 1)),
    womens          INTEGER       NOT NULL CHECK (womens IN (0, 1)),
    zip_code        VARCHAR       NOT NULL CHECK (zip_code IN ('Urban', 'Suburban', 'Rural')),
    newbie          INTEGER       NOT NULL CHECK (newbie IN (0, 1)),
    channel         VARCHAR       NOT NULL CHECK (channel IN ('Phone', 'Web', 'Multichannel'))
);

-- Which group each customer was randomly assigned to.
CREATE TABLE campaign_assignment (
    customer_id INTEGER PRIMARY KEY,
    treatment       VARCHAR       NOT NULL CHECK (treatment IN ('mens_email', 'womens_email', 'no_email')),
    FOREIGN KEY (customer_id) REFERENCES customers (customer_id)
);

-- What happened in the two weeks AFTER the campaign.
CREATE TABLE campaign_outcomes (
    customer_id INTEGER PRIMARY KEY,
    visit       INTEGER       NOT NULL CHECK (visit IN (0, 1)),
    conversion  INTEGER       NOT NULL CHECK (conversion IN (0, 1)),
    spend       DECIMAL(10,2) NOT NULL CHECK (spend >= 0),
    FOREIGN KEY (customer_id) REFERENCES customers (customer_id)
);

-- Fill the tables
-- rowid is DuckDB's internal row number (0, 1, 2, ...) in file order,
-- so rowid + 1 gives each customer the same ID in all three tables.
INSERT INTO customers (customer_id, recency, history,
                       mens, womens, zip_code, newbie, channel)
SELECT
    rowid + 1,
    recency,
    history,
    mens,
    womens,
    CASE WHEN zip_code = 'Surburban' THEN 'Suburban' ELSE zip_code END,  -- typo in the source file
    newbie,
    channel
FROM raw_hillstrom;

INSERT INTO campaign_assignment (customer_id, treatment)
SELECT
    rowid + 1,
    CASE segment
        WHEN 'Mens E-Mail'   THEN 'mens_email'
        WHEN 'Womens E-Mail' THEN 'womens_email'
        WHEN 'No E-Mail'     THEN 'no_email'
    END  -- an unexpected label becomes NULL, and NOT NULL stops the load
FROM raw_hillstrom;

INSERT INTO campaign_outcomes (customer_id, visit, conversion, spend)
SELECT rowid + 1, visit, conversion, spend
FROM raw_hillstrom;

-- 3. Convenience view: one row per customer, everything joined.
------------------------------------------------------------------------
CREATE VIEW analysis_base AS
SELECT
    c.*,
    a.treatment,
    o.visit,
    o.conversion,
    o.spend
FROM customers           AS c
JOIN campaign_assignment AS a USING (customer_id)
JOIN campaign_outcomes   AS o USING (customer_id);