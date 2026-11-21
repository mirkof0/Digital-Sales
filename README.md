# Who should get the email?

An online retailer emailed some customers and not others, chosen at random. This project measures what the email
changed, finds out for whom it works best, and decides whether it pays to email only some customers instead of
everyone.

<!-- Add the link to the Streamlit app here once it is deployed, e.g.:-->
**Project summary (interactive):** https://uplift-modeling-00.streamlit.app/ 

## Key results

- **The men's email works.** In the two weeks after the campaign it raised the visit rate from 10.6% to 18.3%
  (+7.7 percentage points, 95% CI +7.0 to +8.3) and revenue per customer by $0.77 (95% CI $0.49 to $1.05).
  The women's email works too, but less (+4.5 percentage points of visits).
- **It works about equally well on everyone, with one exception.** Of six customer features, only one changes the
  effect: the kind of products a customer buys. Customers who bought both men's and women's products gain
  +13.4 percentage points from the men's email, against about +7 for everyone else.
- **An uplift model adds nothing over that simple rule.** A T-learner made of two logistic regressions ranks
  customers no better than "'Both' buyers first" (Qini coefficient 3.3 vs 3.1 extra visits per 1,000 customers; the
  difference is not significant). Its top 10% are exactly the "Both" buyers.
- **Recommendation** (at a 50% margin): if an email costs less than $0.33, email everyone; between $0.33 and $0.91,
  email only the "Both" buyers; above $0.91, don't email.

## The data

Kevin Hillstrom's [MineThatData E-Mail Analytics and Data Mining Challenge](http://www.minethatdata.com/Kevin_Hillstrom_MineThatData_E-MailAnalytics_DataMiningChallenge_2008.03.20.csv)
(2008): 64,000 customers of an online clothing retailer who bought something in the past year, split at random into
three equal groups: an email advertising men's merchandise, an email advertising women's merchandise, and no email.

- **Observed for two weeks after the campaign:** did the customer visit the website, did they buy, and how much did
  they spend.
- **Known from before:** months since the last purchase, last year's spend, whether they bought men's, women's or
  both kinds of merchandise, how they order (phone, web or both), whether they are a new customer, and the area they
  live in.

Because the groups were formed at random, any difference between them is caused by the email (an A/B test).

## Approach

| Phase | Notebook | What it does |
|---|---|---|
| 1 | [phase1](notebooks/phase1.ipynb) | Download the data, load it into a DuckDB database with SQL, run data quality checks |
| 2 | [phase2](notebooks/phase2.ipynb) | A/B test readout: check the random split (group sizes, similar customers), then the lift of each email on visits, purchases and revenue, with confidence intervals and the Holm correction for multiple testing |
| 3 | [phase3](notebooks/phase3.ipynb) | Segments: the lift in 17 segments of 6 customer features, and interaction tests of whether it differs between them |
| 4 | [phase4](notebooks/phase4.ipynb) | Uplift model: a T-learner of two logistic regressions, cross-fitted, compared with a response model and the buyer-type rule using Qini curves with bootstrap intervals; then profit by share of customers emailed |

The project summary page (`app/`) presents the results for non-technical readers, with a simulator for the cost per
email, the margin and the share of customers emailed.

## How to run

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync                                     # install the environment
uv run digital-sales                        # download the data, build the database, run every phase, write results/
uv run streamlit run app/streamlit_app.py   # open the project summary page
```

## Repository layout

```
src/digital_sales/   analysis code: data loading, A/B readout, segments, uplift model, and the pipeline
sql/                 SQL for loading the data, quality checks and customer segments
notebooks/           phases 1-4, with the reasoning and explanations
results/             small result tables written by the pipeline; the summary page only reads these
app/                 Streamlit project summary page
```

## Limitations

- Only two weeks were observed: long-term effects, such as unsubscribes or later purchases, are unknown.
- The data come from one retailer in 2008; the results carry over only to similar customers and emails.
- The margin and the email costs are assumptions; the summary page lets you change them.
- Revenue is noisy because only about 1 customer in 100 buys, so revenue results are less certain than visit results.
- The "Both" flag and the model's features were chosen after looking at these same customers, so the model's scores
  are slightly optimistic.
