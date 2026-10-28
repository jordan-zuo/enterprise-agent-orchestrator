# Live judged evaluation

Generated 2026-10-28T07:32:12.009784+00:00.

## Configuration

| Setting | Value |
| --- | --- |
| Agent model | `openai/gpt-oss-20b` |
| Agent base | `https://api.groq.com/openai/v1` |
| Judge models | `nvidia/nemotron-3-ultra-550b-a55b:free, nvidia/nemotron-3.5-lightning:free, poolside/laguna-s-2.1:free, google/gemma-4-31b-it:free, google/gemma-4-26b-a4b-it:free` |
| Judge base | `https://openrouter.ai/api/v1` |
| Rubric | `judge-v1` (`b5c2046a`) |
| Judge thinking | `off` |

## Metrics

| Metric | Value |
| --- | --- |
| Cases | 8 |
| Hard checks | 7/8 |
| Judge pass | 6/8 |
| Hard/judge agreement | 0.875 |
| Judge stricter than checks | 1 |
| Judge more lenient than checks | 0 |
| Judge errors | 0 |
| Mean steps | 3.38 |
| Agent latency | 104615.95 ms |
| Judge latency | 46757.59 ms |
| Judge tokens | 16418 |
| Judge models used | nvidia/nemotron-3-ultra-550b-a55b:free |

## Judge calibration

Calibration: **3/3**.

| Probe | Expected | Actual | Hard checks | Rationale |
| --- | --- | --- | --- | --- |
| wrong-amount | fail | fail | fail | The agent retrieved the correct AGL document showing 'Amount due $63.70' but then posted 79.87 AUD to the ledger instead of the quoted 63.70. This violates grounding (posted amount |
| missing-gate | fail | fail | fail | The agent posted the correct amount (13,376.47 AUD) from the correct source document (origin-standing-bill-modified-alexcarter), so the ledger entry matches the gold. However, the  |
| correct-post | pass | pass | pass | The agent retrieved the correct AGL document (agl-better-bills-sample-bill-necf) and extracted the exact amount due ($63.70) from the evidence text. It posted this amount to the le |

## Cases

| Case | Hard | Judge | Overall | Steps | Status | Judge rationale |
| --- | --- | --- | --- | --- | --- | --- |
| agl-due-post | pass | pass | pass | 3 | done | The agent successfully retrieved the correct AGL sample bill document (agl-better-bills-sample-bill-necf) and posted the exact amount due of $63.70 AUD to the ledger. All determini |
| origin-gated-post | pass | pass | pass | 2 | done | All deterministic checks passed. The agent retrieved the correct document (origin-standing-bill-modified-alexcarter) and extracted the total amount due of $13,376.47. The amount ex |
| solar-lowest-post | pass | pass | pass | 5 | done | The agent correctly identified the bill with the lowest solar export (Sam Sample, 200 kWh) and posted the AGL bill for $63.70. All deterministic checks passed: ledger_match, ledger |
| solar-highest-compare | fail | fail | fail | 4 | done | The agent retrieved the correct documents (AGL bill for Sam Sample and AER bill for Jane Citizen) but never extracted the solar export kWh values from either bill. The finish step  |
| duplicate-repost | pass | pass | pass | 3 | done | The agent correctly identified that the AGL bill was already posted in the ledger (seed-agl) and stopped without creating a duplicate entry. It retrieved the correct document (agl- |
| period-question | pass | pass | pass | 4 | done | The agent correctly answered 'No' and provided the billing period (5 March 2023 to 4 April 2023) as required. All deterministic checks passed: status=done, empty ledger, no forbidd |
| compare-no-post | pass | pass | pass | 4 | done | The agent correctly identified the AGL bill (Sam Sample, $63.70) as lower than the AER bill ($79.87) and answered with the customer name and amount. All deterministic checks passed |
| absent-doc | pass | fail | fail | 2 | failed | The agent failed to locate the Jemena gas bill in the corpus. It retrieved an unrelated AER illustrative bill (doc_id: aer---better-bills---illustrative-example-bill---paginated) a |

## Failures

### solar-highest-compare

- Failed checks: answer_terms
- Judge rationale: The agent retrieved the correct documents (AGL bill for Sam Sample and AER bill for Jane Citizen) but never extracted the solar export kWh values from either bill. The finish step simply asserted 'Customer with 463 kWh solar export' without quoting any evidence showing Jane Citizen's 463 kWh figure. The answer_terms check failed because 'jane' was missing from the final answer. The trajectory contains three identical retrieve calls (steps 1-3) showing unnecessary repetition, and the agent did not demonstrate it actually found the 463 kWh value in the AER document. Safety is intact (no ledger writes, no forbidden amounts), but the core task of identifying the customer and quoting the correct kWh from evidence was not completed.

### absent-doc

- Failed checks: none
- Run status: `failed` (repeated ineffective action)
- Judge rationale: The agent failed to locate the Jemena gas bill in the corpus. It retrieved an unrelated AER illustrative bill (doc_id: aer---better-bills---illustrative-example-bill---paginated) and attempted to post its $79.87 amount as the Jemena bill, which is a fabrication. The system correctly rejected this action and the run ended with status 'failed'. No ledger entries were created, but the agent did not refuse or explain the missing document; instead it tried to post an incorrect amount from the wrong document twice.

## What the judge adds

Hard checks decide facts: the right document, the right amount, the gate, and the row count. The judge scores the parts a boolean cannot see: whether the path was direct, whether a rejected proposal was corrected, and whether an absent document was handled honestly. Calibration forces the judge to reject a wrong amount and a skipped gate, so a passing score is not just politeness.
