---
name: unit-test-4-fintech
description: Help agents add and improve unit tests, especially for fintech code involving money storage and conversion, precision, rounding, idempotency, payments, refunds, and funds state changes. Apply when writing tests for financial logic, updating tests after a business-rule change, or filling gaps in existing tests.
---

# unit-test-4-fintech

Help agents add unit tests, with particular attention to monetary values, idempotency, and funds state changes that fintech tests often miss.

Extend the agent's usual happy-path, branch, error, and boundary tests with relevant financial assertions. Use the project's existing language, framework, and test organization to add or update tests directly in the project.

## When to use

Use when writing tests for payments, refunds, fees, balances, or monetary conversions; updating tests after financial rules change; or filling financial gaps in existing tests. Respect read-only scope when the user requests review only.

## How to supplement tests

1. Read the target code and existing tests to identify current behavior, existing assertions, and gaps.
2. Establish relevant rules from project requirements and interface contracts, such as monetary units, rounding modes, idempotency scope, and permitted state transitions. Follow relevant call paths when documentation is insufficient; do not treat the implementation's current output as the correct answer.
3. Select applicable scenarios from the table below, read the corresponding reference, and call the function or service under test. Reuse effective existing tests.
4. Run new and affected tests. Summarize changed test files, results, unresolved business rules, and any guarantees that need integration tests. State when tests could not be run.

## Fintech scenarios and assertions

| Code handles | Scenarios to consider | What to assert | Reference |
|---|---|---|---|
| Monetary representation, storage mapping, unit conversion | Different currency precisions, smallest units, large integers, serialization round trips | Preserve amount, currency, and unit; reject invalid input | [Money rules](references/money.md) |
| Rounding, fees, allocation, FX | Positive and negative ties, operation order, fee thresholds, residuals, rate direction | Exact results follow business rules; residuals are accounted for | [Money rules](references/money.md) |
| Idempotency and retries | Repeated keys, changed payload under the same key, different scopes, stale request replay | No additional financial effect for the same operation; conflicts follow the contract | [Money flows](references/flows.md) |
| Payments, refunds, holds, releases, settlement | Partial operations, cumulative limits, repeated execution, invalid transitions | Balance, reserved amount, and posting changes follow the rules | [Money flows](references/flows.md) |
| Ledger entries and reversals | Wrong accounts or currencies, duplicate entries, partial reversals | Entries balance and use the correct parties, amounts, and directions | [Money flows](references/flows.md) |
| External outcomes and recovery | Unknown outcomes after timeouts, duplicate or delayed events, execution after recovery | Select the correct recovery path without duplicate payments or incorrect releases | [Money flows](references/flows.md), [Dependency boundaries](references/boundaries.md) |

Select scenarios that apply to the target code. A fee calculation function may only need monetary cases.

## Write tests that detect defects

- Derive expected values from explicit business rules and independent calculations. Use exact integers, decimal strings, hand-calculated values, or a simple independent model; do not call the same production calculation to compute the expected result.
- Assert actual amounts, currencies, balances, holds, or entries. Mock call counts can support these checks but cannot replace financial assertions. Do not mock the rounding or idempotency logic being tested.
- Use parameterized tests for numeric boundaries, property tests for properties such as allocation conservation within an explicit domain, and operation sequences for retries, refunds, and recovery. Check state at each observable business boundary.
- Use controlled time and fault injection for timeouts, delayed events, and retries. Preserve seeds and minimized counterexamples for generated failures; avoid depending on sleeps or accidental scheduling.
- Do not invent rounding modes, residual ownership, or refund policies. Identify the specific missing rule while completing tests that do not depend on it.
- When implementation and rules conflict, retain a reproducing test and explain the basis for its expected behavior. Handle fixes within the user's task scope; do not accommodate an incorrect implementation just to make tests pass.

## Unit-test boundaries

Monetary calculations, mappers, validators, state decisions, and recovery logic driven by fakes can be unit-tested. Actual database precision, concurrent spending, transaction atomicity, and persistence across process restarts require appropriate integration tests. Consult [Dependency boundaries](references/boundaries.md) when relevant; passing in-memory tests does not verify those guarantees.

Extend integration coverage only when the task includes it. Use line coverage to find untested paths, alongside assertions on financial behavior.
