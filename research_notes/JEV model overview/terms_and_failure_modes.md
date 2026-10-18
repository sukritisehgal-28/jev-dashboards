# TypeSafe terms on benchmarking, and where Jev is documented to lose

Checked 2026-10-12. Not legal advice.

## Terms: can we publish benchmark results?

Sources: [Master Customer Agreement](https://typesafe.ai/legal/mca), [Acceptable Use Policy](https://typesafe.ai/legal/acceptable-use-policy) (last updated 2026-09-23).

**Neither the MCA nor the AUP mentions benchmarking, evaluation, or publishing performance results.** There is no "no-benchmarking" clause.

Clauses that constrain how we run and publish the evaluation:

| Clause | Text (abridged) | What it means for us |
|---|---|---|
| MCA 2.3(b) | No "model distillation, train a model to imitate the output of the Services", no developing "a similar or competing product" | Never train on Jev outputs. Don't release a bulk dump of raw Jev outputs; publish metrics plus code so others rerun with their own key. |
| MCA 2.3(g)(2) | No "security or vulnerability test" | Keep prompt-injection and attack tests out of the published study. Option-order and option-name perturbations are accuracy tests, not security tests. |
| AUP 3.4 | Don't "intentionally drive TypeSafe's AI model to act in a manner that contravenes TypeSafe's policies" | Same: no jailbreak-style testing. |
| AUP 3.7 | Don't "probe, scan, penetrate, or test the vulnerability" of systems | Same. |
| MCA 2.3(j), 2.3(f) | Don't exceed usage limits or interfere with the Services | Throttle the eval harness and stay under rate limits. |
| MCA 4.1–4.2 | Outputs are Customer Data and are assigned to the customer | We own our results. |
| MCA 14.1 | TypeSafe Confidential Information includes Documentation and "other non-public information with respect to the Services" | Small gray area: measured performance could arguably count. 14.3(a) excludes public information. Low risk; resolve with a written OK. |
| MCA 16.4 | No use of the other party's name, brand, or logo; no public announcement that the parties have an agreement | No logo and no implied endorsement. Naming Jev factually in a write-up is normal, but this clause is the main reason to ask first. |

**Action:** email TypeSafe before publishing, saying we plan to publish an independent accuracy/calibration study with our own data and code. A written OK removes the 14.1 and 16.4 ambiguity.

## Where Jev is documented to lose

### Vendor-acknowledged ([Jev 1.13 jaggedness](https://docs.typesafe.ai/model-jaggedness/jev-1.13), reviewed 2026-10-02)

1. **Literal reading.** Scoping words, negations, and implied conditions are taken at face value.
2. **Math and numbers.** Counting is unreliable; numeric representations (hex, RGB, binary) underperform; Score levels are "weak in numerical calibration", so use them only against thresholds.
3. **Dates and times.** Dates are read as text, so ordering, duration, and window checks are unreliable, worse with mixed formats.
4. **Indirection.** Double negatives and multi-hop reasoning reduce accuracy.
5. **Large irrelevant state** distracts the model.
6. **Adversarial content.** Injected instructions or self-arguing text can change answers.
7. **Contradictory criteria**, e.g. a Noul where true maps to "no".
8. **Option order.** Leans toward the first option.
9. **Generation.** Not supported.

### Independent ([arXiv:2609.26758](https://arxiv.org/abs/2609.26758), Sun et al., v3 2026-10-08)

"Type-Safe Is Not Error-Free": typed decision models follow the **option name** rather than the definition bound to it. With yes/no option names, flip rates were up to 70.4 pp higher than a 0/1 control. Reassigning definitions dropped mean AUC from 93.8% to 23.2% (below chance). The type-error rate was 0%. The abstract says it tests "Jev and two open-weight models"; confirm in the full paper that this is TypeSafe's Jev.

No independent calibration study was found. [AnyJev](https://wavect.io/blog/anyjev-calibration-option-order-bias/) is an unaffiliated look-alike library, not Jev.

## Predicted losses for our project (hypotheses to test, not results)

| Hypothesis | Why we expect it | Experiment |
|---|---|---|
| H1: Jev loses to rules and Sherlock on **numeric-only columns** (ID vs count vs money vs year) | Numbers weakness | Stratify accuracy by column dtype |
| H2: **Misleading headers** beat cell values (a column named `revenue` holding refunds) | Option- and name-following | Build a "headers lie" subset with swapped or misleading headers |
| H3: **Option order** changes field mapping | First-option bias | Shuffle the standard-field list 5×; report flip rate |
| H4: Accuracy drops on **wide tables** if sent whole | Irrelevant state | One column per call vs whole table |
| H5: **Mixed date formats** are typed fine, but time-window decisions fail | Date weakness | Keep all date logic in code; test Jev only on date-part extraction |
| H6: **Score** confidence is poorly calibrated vs Choice/Noul | Vendor says Score is numerically weak | Separate reliability diagrams per question type |

Prompt-injection-in-cells is a real product risk for user-uploaded data, but per MCA 2.3(g) and AUP 3.4 we handle it defensively in code and leave it out of the published benchmark unless TypeSafe approves.
