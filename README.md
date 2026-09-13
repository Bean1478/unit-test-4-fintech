# unit-test-4-fintech

[English](README.md) | [简体中文](README.zh-CN.md)

**A unit testing Skill for fintech scenarios.**

unit-test-4-fintech helps coding agents add unit tests for money handling, idempotency, payments, refunds, and recovery. The agent updates your test suite and runs new and affected tests using your project's language, test framework, and business rules.

A test can execute a payment path without checking whether a retry charges twice, a conversion loses a minor unit, or a partial refund exceeds the remaining refundable amount. The skill guides the agent to add assertions for these behaviors alongside ordinary happy-path, branch, and error tests.

[Read the skill](SKILL.md) · [Run the demo](examples/demo.py)

## When to use it

| Your task | Example request | Tests the skill helps the agent add |
|---|---|---|
| Test a new financial feature | "Write unit tests for this refund service." | Successful and rejected refunds, cumulative limits, duplicate requests, and refunds posted to the correct account |
| Update tests after a rule change | "Fees now have a minimum and a cap. Update the tests." | Thresholds, rounding ties, operation order, and historical-rule behavior where applicable |
| Supplement an existing test suite | "Review this payment module's tests and add missing financial scenarios." | Relevant gaps such as precision loss, retry conflicts, partial settlement, and recovery after an unknown outcome |

It also applies to financial logic in commerce, wallets, billing, and other applications that handle money. If you request review only, the agent provides code-specific findings and suggested tests.

## What it helps the agent test

The references provide test inputs, expected values, retry sequences, and examples of provider timeouts and failed writes.

| Target logic | Cases to add | Financial assertions | Guidance |
|---|---|---|---|
| Money parsing, storage mapping, and conversion | Different currency exponents, smallest units, large integers, excess precision, serialization | Exact amount, asset, and unit survive supported conversions; invalid values follow the contract | [Representation and boundaries](references/money.md#m-01-representation-and-boundaries) |
| Rounding, fees, and allocation | Positive and negative ties, rounding order, minimum fees and caps, residual distribution | Exact fees and recipient shares; residuals are accounted for once | [Rounding](references/money.md#m-02-quantization-and-rounding), [fees and allocation](references/money.md#m-03-allocation-fees-and-residuals) |
| FX conversion | Quote direction, source and target exponents, expiration, fees, output quantization | Correct assets and converted amount under the selected quote | [Assets and FX](references/money.md#m-04-assets-and-fx) |
| Idempotency and retries | Same key and payload, changed payload, tenant scope, replay after state changes | One financial effect per logical operation; valid distinct operations remain distinct | [Idempotency contracts](references/flows.md#f-01-idempotency-contracts) |
| Holds, captures, and releases | Partial settlement, remaining hold release, repeated capture, stale reserve requests | Correct posted, held, and available balances after each step | [Holds and state machines](references/flows.md#f-02-holds-and-state-machines) |
| Refunds, ledger entries, and reversals | Cumulative refund limits, retries after full refund, partial reversals, wrong accounts or currencies | Correct recipients, balanced posting groups, original-operation links, and no duplicate financial effects | [Ledgers and reversals](references/flows.md#f-03-ledgers-and-reversals) |
| Provider calls and recovery | Provider accepts a payment but its response is lost; local confirmation fails; recovery repeats | Recover the original transaction, settle once, and resolve holds according to the contract | [Interruption and recovery](references/flows.md#f-04-interruption-and-recovery) |
| Webhooks and messages | Duplicate events for one capture, distinct partial captures, stale events, publish acknowledgment loss | Apply each financial operation once while preserving legitimate later operations | [APIs and webhooks](references/boundaries.md#b-02-apis-and-webhooks), [messaging](references/boundaries.md#b-03-outbox-and-messaging) |
| Reconciliation, time, and permissions | Amount or currency mismatches, expiry boundaries, historical fee versions, authorization on retries | Correct discrepancies and policy versions; rejected requests do not debit or credit accounts | [Reconciliation](references/boundaries.md#b-04-reconciliation), [time and permissions](references/boundaries.md#b-05-time-policies-and-permissions-when-relevant) |

Select cases relevant to the target code. Each example states its assumptions; adapt the inputs and expectations to your project's rules.

## How the agent supplements your tests

The agent reads the code and existing tests, identifies missing cases, and adds assertions based on independently calculated expectations. Tests call the function or service under test and check amounts, balances, and postings. The agent then runs new and affected tests and reports the results, including any tests it could not run.

If a business rule is unclear, the agent identifies what needs clarification and continues with other cases. If the implementation contradicts an established rule, it keeps the failing test and explains the discrepancy.

## Example: add a duplicate-payment test

Here, `Wallet` stands for either wallet implementation in the demo. In your project, call the payment function or service being tested.

**Check a single successful payment:**

```python
wallet = Wallet(balance_minor=10000)
wallet.charge('12.34', exponent=2, key='payment-1')

assert wallet.balance_minor == 8766
assert len(wallet.postings) == 1
```

**Add the idempotency rule and process the same request twice:**

```python
wallet = Wallet(balance_minor=10000)
first = wallet.charge('12.34', exponent=2, key='payment-1')
retry = wallet.charge('12.34', exponent=2, key='payment-1')

assert wallet.balance_minor == 8766  # Only 1234 is deducted, even after the retry
assert len(wallet.postings) == 1    # A single posting
assert retry['posting_id'] == first['posting_id']
```

With the idempotency check missing, the first test passes. The second detects a balance of `7532`: the same request charged the account twice.

The same approach extends to sequences in the references: replaying an old refund after the refundable amount is exhausted, releasing the remainder of a partially captured hold, or resuming a payment whose provider response was lost.

## Run the demonstration

The [demo](examples/demo.py) tests currency conversion, HALF_EVEN rounding, and payment retries against defective and corrected in-memory wallets. It uses the Python 3 standard library. Run it from the `unit-test-4-fintech/` directory:

```bash
python examples/demo.py
```

Observed output:

```text
Basic example / buggy code: 1 passed, 0 failed, 0 errors
Fintech examples / buggy code: 1 passed, 3 failed, 0 errors
  FAIL test_currency_exponent
  FAIL test_duplicate_request
  FAIL test_half_even_rounding
Fintech examples / fixed code: 4 passed, 0 failed, 0 errors
Demo reproduced: all three intentional defects were detected.
```

| Intentional defect | Single-payment test | Added financial assertion | Defective result → Contract expectation |
|---|---|---|---|
| Ignore currency configuration and always multiply by 100 | Passes | Convert using the configured exponent | `1.234`, exponent=3: `123` → `1234` |
| Use HALF_UP where HALF_EVEN is required | Passes | Check a rounding tie | `1.005`, exponent=2: `101` → `100` |
| Charge again for the same key | Passes | Check balance and posting count after a retry | Balance `7532` → `8766`; two postings → one |

The demo contract explicitly requires HALF_EVEN, a configured exponent, and one financial effect for retries with the same key. The script exits successfully only when the three expected failures occur on the defective version and all four tests pass on the corrected version.

The demo covers the three cases above. Tests generated by agents with and without the skill have not yet been compared.

## Unit-test boundaries

Unit tests can check calculations, parsers, mappers, validators, state transitions, and recovery decisions using controlled dependencies. Actual database precision, concurrent spending, transaction atomicity, and durability across restarts need integration or system tests. [Dependency boundaries](references/boundaries.md#b-01-databases-and-concurrency) explains which assertions belong at each layer.

The agent identifies these integration gaps and adds integration tests when requested. Line coverage helps locate untested paths; financial assertions check the expected behavior.

## Package contents

| File | Purpose |
|---|---|
| [README.md](README.md) / [README.zh-CN.md](README.zh-CN.md) | English and Simplified Chinese usage guides |
| [SKILL.md](SKILL.md) | Agent instructions and reference selection |
| [references/money.md](references/money.md) | Monetary representation, rounding, fees, allocation, and FX cases |
| [references/flows.md](references/flows.md) | Idempotency, holds, refunds, ledger, and recovery sequences |
| [references/boundaries.md](references/boundaries.md) | Dependency setups and assertions for adapters, webhooks, messaging, reconciliation, time, and permissions |
| [examples/demo.py](examples/demo.py) | Runnable illustration of three financial defects and their detecting tests |
