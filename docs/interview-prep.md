# Interview preparation guide

[Project overview](../README.md) · [Data model and metrics](data-model.md) · [Power BI report](report.md) · [Runbook and progress](operations.md)

A study plan and quiz bank for explaining this project in a Senior Analyst, Digital Marketing interview. Every figure below comes from the verified Gold snapshots; the data is synthetic.

## How to study

Answer one question at a time, out loud, in 30 seconds or less. Then compare with the model answer and add any miss to [weak spots](#weak-spots-to-review). Say the answer first, then one number, then the next action.

| # | Round | Focus | Status |
|---:|---|---|---|
| 1 | Business | The decision the project supports; Margin ROAS | Done (Q1–Q2) |
| 2 | Metrics | CTR, CVR, CPA, ROAS, Margin ROAS; reading a weak funnel | Done (Q3–Q4) |
| 3 | A/B test | Intent-to-treat, lift, confidence interval, power | In progress (Q5–Q8) |
| 4 | Findings | Loss-making campaigns, `CMP003`, attributed versus incremental | Not started |
| 5 | Pipeline | Bronze → Silver → Gold, joins, quality gate | Not started |
| 6 | Mock interview | Full walkthrough and follow-up questions | Not started |

## 60-second pitch

> "A travel marketplace buys traffic from five metasearch channels in Thailand, Indonesia, and Singapore. I asked two questions: where does ad spend earn margin, and do ads actually create bookings? I generated linked synthetic clicks, sessions, bookings, and a separate randomized experiment, loaded them into BigQuery, built Bronze, Silver, and Gold layers in Dataform with 23 quality assertions that block Gold if checks fail, and built a four-page Power BI report. USD 28K of spend produced USD 37K of gross margin, a 1.32× Margin ROAS. But 5 of 15 campaigns lose money, mostly flight channels where commission is only 7%. The worst is `CMP003`, Thailand Skyscanner: high click-through but a 1.75% conversion rate, losing USD 2.8K. The experiment shows ads lift conversion by about 0.9 points, but only about 15% of Treatment bookings were incremental, so attributed return probably overstates real return. I would investigate `CMP003`'s landing experience before cutting it and test flight channels for incrementality before scaling them."

## Key numbers

| # | Topic | Value |
|---:|---|---|
| 1 | Funnel | 1,102,402 impressions → 39,171 clicks → 35,377 sessions → 1,792 confirmed paid bookings |
| 2 | Rates | CTR 3.6%; session rate 90.3%; CVR 4.6%; CPC USD 0.72; CPA USD 15.66 |
| 3 | Money | Spend USD 28,062; booking value USD 296,590; gross margin USD 37,081; contribution USD 9,019 |
| 4 | Returns | ROAS 10.6×; Margin ROAS 1.32× |
| 5 | Commission | Hotel 15%, flight 7%, activity 19%; a flight needs ROAS above 14.3× to break even |
| 6 | Loss-making campaigns | `CMP003` TH Skyscanner −2,809; `CMP013` SG Skyscanner −581; `CMP012` SG Google Flights −435; `CMP008` ID Skyscanner −364; `CMP007` ID Google Flights −132 (USD) |
| 7 | `CMP003` | CTR 6.3% (peers ≈ 3.3%); CVR 1.75% (Thai peers ≈ 6.0–6.9%); CPA USD 44.94; Margin ROAS 0.27; mobile is USD −2,253 of the loss |
| 8 | Experiment | 15 tests × 5,000 users per arm; Treatment 5.85% vs Control 4.97%; +0.88 points; 95% CI 0.65–1.10 points; +17.6% relative lift; 656 incremental conversions |
| 9 | Experiment caution | 8 of 15 single-test intervals include zero; each test detects only about 1.2 points reliably |

## Quiz bank

### Round 1 — Business

**Q1. What is the main business question?**
> "Which markets, channels, and devices earn enough margin to justify their ad spend, and did the ads actually create additional bookings?"

**Q2. Why use Margin ROAS instead of ROAS?**
> "ROAS uses booking value, but the company keeps only its commission. Margin ROAS is gross margin divided by ad spend, so it shows whether ads make money. ROAS is 10.6× here, while Margin ROAS is only 1.32×."

Do not confuse this with incrementality: Margin ROAS answers *profit*; the A/B test answers *cause*.

### Round 2 — Metrics

**Q3. What is CVR, and what counts as a conversion?**
> "CVR is confirmed paid bookings divided by clicks. A booking counts only when `booking_status = 'confirmed'` and `payment_status = 'paid'`; cancelled and pending bookings do not."

CTR = clicks ÷ impressions. CVR = bookings ÷ clicks.

**Q4. `CMP003` has high CTR and low CVR. What does that mean, and what would you check?**
> "The ad attracts clicks, but visitors do not book. About 90% of clicks still reach the site, like its peers, so the leak is after landing. It loses USD 2.8K. I would check price and offer match between ad and site, landing page speed and errors, the mobile experience, which drives most of the loss, and compare it with Thai peers converting at about 6%."

### Round 3 — A/B test

**Q5. Why divide by all assigned users rather than only clickers?**
> "Randomization makes only the whole groups comparable. Control cannot click the test ad, and clickers already have high intent, so a clicker-only rate would overstate the lift. Dividing by every assigned user is intent-to-treat."

**Q6. Treatment 5.85% versus Control 4.97%: what is the lift?**
> "Absolute lift is 0.88 percentage points. Relative lift divides by Control, the baseline: 0.88 ÷ 4.97 = 17.6%."

Dividing by Treatment (0.88 ÷ 5.85 = 15%) gives the share of Treatment conversions caused by the ad, not the relative lift.

**Q7. Eight single-test 95% intervals include zero. What does that mean, and why?**
> "Each single test cannot rule out zero effect. The tests are underpowered: 5,000 users per arm at about a 5% conversion rate can reliably detect only about a 1.2-point lift, while the true lift is about 0.9 points. Pooled across 15 tests, the result is clear."

**Q8. How could one test detect a smaller lift?**
> "Increase the sample size, with more users or a longer test, or reduce noise, for example by adjusting for pre-test behaviour (CUPED). Accepting lower confidence also works but raises false positives."

### Round 4 — Findings

**Q9. Which campaigns lose money, and what do they have in common?**
> "Five of 15 have negative contribution. Apart from `CMP003`, all are Google Flights or Skyscanner in Indonesia or Singapore. Flights earn only 7% commission, so they need about 14× ROAS just to break even."

**Q10. Is a 1.32× Margin ROAS good news?**
> "It is positive on an attributed basis: USD 9K contribution. But attribution credits every booking that came through an ad. The experiment suggests only about 15% of Treatment bookings were incremental, so the causal return is probably much lower. The experiment is a separate population, so I would use it as a warning and a reason to test, not to restate campaign margin."

**Q11. What would you recommend to the marketing lead?**
> "Do not cut `CMP003` blindly: fix the landing and mobile experience first, then re-measure. Cap or test flight channels in Indonesia and Singapore. Scale hotel and activity channels only after a larger incrementality test confirms the lift in that market and channel."

### Round 5 — Pipeline

**Q12. What do Bronze, Silver, and Gold do?**
> "Bronze stores source-shaped data as loaded. Silver casts types, standardizes values, and validates keys and relationships. Gold aggregates KPI-ready marts for reporting."

**Q13. Why aggregate clicks and bookings before joining to platform data?**
> "The platform table is already one row per date, market, channel, campaign, and device. Joining it to click-level rows would repeat impressions and spend for every click and inflate them. Aggregating first keeps one row per grain."

**Q14. How does the pipeline stop bad data from reaching the report?**
> "Gold depends on upstream Dataform assertions. If a check fails, such as click-to-session integrity or booking reconciliation, Dataform skips the Gold rebuild and keeps the last good table. The first run caught 28 margin rounding errors this way."

**Q15. Why attribute bookings to the click date?**
> "A booking can happen up to 72 hours after the session. Attributing it to the click date keeps spend and the bookings it produced in the same row."

### Round 6 — Mock interview prompts

1. Walk me through the project in two minutes.
2. Why synthetic data, and how did you make it realistic?
3. What would you change to run this in production?
4. What is the weakest part of your analysis?
5. How would you design the next incrementality test?
6. How do you know the dashboard numbers are right?

## Weak spots to review

| # | Mistake seen in practice | Correct idea |
|---:|---|---|
| 1 | Explained Margin ROAS as an incrementality measure | Margin ROAS measures profit; the A/B test measures cause |
| 2 | Described CTR when asked for CVR | CVR = confirmed paid bookings ÷ clicks |
| 3 | Divided relative lift by Treatment | Relative lift divides by Control |
| 4 | Could not explain intervals that include zero | Single tests are underpowered; pooled result is clear |
| 5 | Delivery | Say "ad", not "app"; say "Margin ROAS" clearly; answer first, then stop |

## Known limitations to admit

1. The Incrementality screenshot comes from a stale Power BI Import cache: it shows the retired aggregate experiment (600K users per arm). Refresh and recapture before presenting it.
2. Report tables do not show their measure columns, so the action queue is not sorted by contribution; the funnel stages sort alphabetically.
3. Synthetic experiment results are unrealistically consistent: every test is positive, and the spread between tests is about five times smaller than random sampling would produce.
4. Gold has no p-values or power fields, and the experiment has no spend, so incremental ROAS cannot be calculated.
5. One month of data, no live ad feed, and no scheduled refresh.
