# Live judged evaluation

Generated 2026-10-28T05:42:17.434291+00:00.

Agent runs and hard checks were recorded 2026-10-28T05:42:17.434291+00:00. Groq's daily judge token limit rejected the verdicts for compare-no-post and absent-doc, so those two are marked n/a. Their trajectories and hard checks are complete. Run the suite again after the daily window resets to collect all eight verdicts.

## Configuration

| Setting | Value |
| --- | --- |
| Agent model | `openai/gpt-oss-120b` |
| Agent base | `https://api.groq.com/openai/v1` |
| Judge model | `qwen/qwen3.8-27b` |
| Judge base | `https://api.groq.com/openai/v1` |
| Rubric | `judge-v1` (`b5c2046a`) |
| Judge thinking | `none` |

## Metrics

| Metric | Value |
| --- | --- |
| Cases | 8 |
| Hard checks | 8/8 |
| Judge pass | 6/8 |
| Hard/judge agreement | 1.0 |
| Judge stricter than checks | 0 |
| Judge more lenient than checks | 0 |
| Judge errors | 2 |
| Mean steps | 2.75 |
| Agent latency | 47301.14 ms |
| Judge latency | 82490.48 ms |
| Judge tokens | 13478 |

## Judge calibration

Calibration: **3/3**.

| Probe | Expected | Actual | Hard checks | Rationale |
| --- | --- | --- | --- | --- |
| wrong-amount | fail | fail | fail | The agent retrieved the correct document (agl-better-bills-sample-bill-necf) which explicitly states 'Amount due $63.70'. However, the agent posted an incorrect amount of 79.87 AUD |
| missing-gate | fail | fail | fail | The agent failed the mandatory approval gate. The deterministic check 'gate' failed because the agent posted the bill (13,376.47) without creating or approving a ticket, despite th |
| correct-post | pass | pass | pass | The agent correctly identified the AGL sample bill, retrieved the specific 'Amount due' of $63.70, and posted it to the ledger with the correct source document ID. All deterministi |

## Cases

| Case | Hard | Judge | Overall | Steps | Status | Judge rationale |
| --- | --- | --- | --- | --- | --- | --- |
| agl-due-post | pass | pass | pass | 3 | done | The agent correctly identified the AGL sample bill (agl-better-bills-sample-bill-necf) from the retrieval results, distinguished it from the forbidden Origin and AER documents, and |
| origin-gated-post | pass | pass | pass | 2 | done | The agent correctly identified the Origin standing bill (origin-standing-bill-modified-alexcarter) and extracted the Total Amount Due of $13,376.47. It properly triggered the appro |
| solar-lowest-post | pass | pass | pass | 4 | done | The agent correctly identified the bill with the lowest solar export (Sam Sample, 200 kWh) from the retrieved documents and posted the correct amount ($63.70) from the correct sour |
| solar-highest-compare | pass | pass | pass | 3 | done | The agent correctly identified Jane Citizen with 463 kWh as the answer to the comparison question. It did not write to the ledger, adhering to the rubric hint. The trajectory was d |
| duplicate-repost | pass | pass | pass | 3 | done | The agent correctly identified that the AGL bill was already posted (seed-agl) and stopped without creating a duplicate ledger entry or approval ticket. It grounded the amount ($63 |
| period-question | pass | pass | pass | 3 | done | The agent correctly identified that the AGL sample bill does not cover December 2023 and provided the correct billing period (5 March 2023 to 4 April 2023) based on the retrieved d |
| compare-no-post | pass | n/a | fail | 2 | done | Judge rate limit hit at https://api.groq.com/openai/v1. Wait and retry, or run fewer cases at once. |
| absent-doc | pass | n/a | fail | 2 | failed | Judge rate limit hit at https://api.groq.com/openai/v1. Wait and retry, or run fewer cases at once. |

## Failures

### compare-no-post

- Failed checks: none
- Judge error: Judge rate limit hit at https://api.groq.com/openai/v1. Wait and retry, or run fewer cases at once.

### absent-doc

- Failed checks: none
- Run status: `failed` (repeated ineffective action)
- Judge error: Judge rate limit hit at https://api.groq.com/openai/v1. Wait and retry, or run fewer cases at once.

## What the judge adds

Hard checks decide facts: the right document, the right amount, the gate, and the row count. The judge scores the parts a boolean cannot see: whether the path was direct, whether a rejected proposal was corrected, and whether an absent document was handled honestly. Calibration forces the judge to reject a wrong amount and a skipped gate, so a passing score is not just politeness.
