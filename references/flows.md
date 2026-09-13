# Idempotency, ledgers, and funds state

Use F-01 for idempotency, F-02 for holds and settlement, F-03 for ledgers and refunds, and F-04 for recovery. Adapt the operation sequences to the project. Amounts are in minor units.

## F-01 Idempotency contracts

Idempotency applies to the financial result of one logical operation. Logs and retry counters may increase.

Consider these dimensions when applicable:

| Scenario | Core assertion |
|---|---|
| Same key and semantically identical payload | References the same business operation; no additional charge, reward, or posting |
| Same key with a different amount, currency, or recipient | Reports or handles the conflict according to the contract; does not silently execute a different second transaction |
| Different keys with the same amount | Two legitimate independent transactions can execute; amount alone must not deduplicate them |
| Same key across tenants or operations | Respects scope without mixing operations or exposing another caller's cached result |
| First request still in progress | Later requests wait, return in-progress status, or conflict as specified; the financial effect remains unique |
| State has already changed | For example, replaying an old hold request after release must not reserve funds again |
| Before and after key expiration | Controlled time verifies the deduplication window; key expiration does not mean an old payment can no longer succeed |
| Retry after restart | Unit tests verify the decision to look up saved records; actual durability belongs to B-01 |

Payload equivalence depends on the protocol: `10.0` and `10.00` may represent the same amount but have different bytes. Test the normalization contract rather than blindly comparing JSON strings.

Distinguish failure classes:

- Validation rejection before execution: no financial effect; whether the error is cached follows the interface contract.
- Definite business rejection, such as insufficient funds: whether the same key can execute after the balance changes is a contractual choice.
- Transient failure with certainty that no external effect occurred: retry according to policy.
- Unknown outcome after a timeout or disconnect: retain a recoverable state and query or safely retry using the same logical identity. Do not assume no debit occurred and switch to a new key.
- External success followed by failed local confirmation: recovery must identify that transaction rather than initiate another financial transaction.

Concurrent duplicates and the atomicity gap between committing funds and saving an idempotency result require B-01. A sequential in-memory map cannot prove these guarantees.

### An idempotency sequence to adapt

Assume an immediate internal transfer without fees. Account A starts at `10000`, and B at `0`. Keys are scoped to the same caller and transfer operation; changing the amount under the same key must conflict. Execute in order:

| Call | A balance | B balance | Successful transfers |
|---|---:|---:|---:|
| K1 transfers 1250 | 8750 | 1250 | 1 |
| K1 repeats the transfer of 1250 | 8750 | 1250 | 1 |
| K1 changes the transfer to 1300 | 8750 | 1250 | 1; returns a payload conflict |
| New key K2 transfers 1250 | 7500 | 2500 | 2 |

Assert balances and successful transfer identities after each step; replay should reference the original transaction. "Successful transfers" counts logical operations, not underlying debit and credit rows. For conflicts, authorization rejections, and insufficient funds, also compare financial state before and after to catch a debit occurring before an error is returned. Do not require audit records, error caches, or retry counters to remain unchanged.

## F-02 Holds and state machines

Define posted, held, and available balances using the project's model. A simple model without credit may use `available = posted - active_holds`; do not impose this on products with credit limits or additional categories of blocked funds.

The following independent vector assumes posted=`10000`, held=`0`, no other movements, and minor units of the same asset:

| Operation | posted | held | available |
|---|---:|---:|---:|
| Reserve `6000` | 10000 | 6000 | 4000 |
| Settle the actual `5500` and release the remaining `500` | 4500 | 0 | 4500 |
| Repeat settlement of the same transaction | 4500 | 0 | 4500 |

### Partial settlement and release

Start independently from posted=`10000`, held=`0`. Assume partial settlement is supported and unsettled funds remain reserved:

| Operation | posted | held | available |
|---|---:|---:|---:|
| Reserve 6000 | 10000 | 6000 | 4000 |
| Capture C1: 2500 | 7500 | 3500 | 4000 |
| Release the remaining 3500 | 7500 | 0 | 7500 |
| Replay the original capture C1 | 7500 | 0 | 7500 |
| Replay the old reserve request | 7500 | 0 | 7500 |

Check hold ownership and status. Capture reduces posted funds once; release frees only the unsettled portion. Also test repeated release, settlement after cancellation, and a new capture request exceeding the remaining hold. Acceptance, rejection, or additional authorization follows the project contract.

Check available funds at authorization time and identify concurrent check-and-reserve atomicity as an integration concern. Two independent requests for `6000` competing for `10000` cannot both receive funds authorization when credit is prohibited.

**Do not treat "balances are never negative" as a universal invariant.** User-initiated authorization and externally completed settlements or chargebacks are different entry points. When external facts exceed the available balance, record them using the project's debt or overdraft model and trigger the prescribed handling. Do not clamp the balance to zero or discard the transaction.

A flow must eventually complete or reach a state with an explicit recovery or handling path. For unknown outcomes, do not release funds blindly to avoid a long-lived hold. Test a controlled recovery driver advancing the flow after dependencies recover, and escalating according to policy when it cannot progress. Finite unit tests cannot prove unconditional eventual completion.

## F-03 Ledgers and reversals

- Check debit-credit balance within a defined book, legal entity, asset or currency, and complete posting group. Do not add bare amounts across currencies or require the sum of all displayed account balances to be zero.
- Balance is only one property. Also check sender, recipient, account type and direction, amount, asset, fee ownership, and business references. Balanced entries posted to the wrong accounts are still wrong.
- For a transaction with multiple entries, assert that the complete group occurs once and no partial group is persisted. Proving the latter at the database level requires integration tests.
- The project's audit contract governs changes or deletion of posted data. For reversals and corrections, verify new records linked to the original transaction and the correct net financial effect.
- Cover full, partial, and repeated reversals, refunds across reporting periods, and amounts exceeding the remaining refundable value. Do not blindly recalculate historical transactions using current fees or FX rates.
- Balance caches and projections may exist. Test rebuilding them from authoritative entries at the same cutoff. For asynchronous projections, assert equality only at the declared synchronization point.
- When old events exist, use sanitized historical fixtures to check amount, asset, timestamp, and projection compatibility. Event replay must not resend historical payments.

### Cumulative refunds and replay

Assume ordinary refunds without fees, a cumulative limit equal to the original transaction's captured `10000`, and a distinct identity for each refund:

| Operation | Total refunded | Remaining refundable | Core assertion |
|---|---:|---:|---|
| Refund R1: 3000 | 3000 | 7000 | Recipient receives 3000, linked to the original transaction |
| Replay R1 | 3000 | 7000 | No second financial effect |
| Refund R2: 7000 | 10000 | 0 | Exactly reaches the cumulative limit |
| Replay R1 again | 10000 | 0 | Still recognizes the original refund; zero remaining funds must not make it look like a new refund |
| New refund R3: 1 | 10000 | 0 | Rejects the excess without changing financial state |

If the original authorization was `15000` but only `10000` was captured, this contract must not allow a refund of `11000` based on the authorized amount. Also test the wrong original transaction, wrong currency, zero or negative refund amounts, and changed amounts under the same refund key, using the applicable contracts.

Check actual refund entries and destination accounts as well as cumulative fields. An assertion on `refunded_total` alone can miss absent payments, payments to the wrong party, or duplicate entries.

## F-04 Interruption and recovery

Choose failpoints from the actual workflow: before or after persisting intent, before sending externally, after external acceptance but before receiving the response, around result recording, between posting and notification, and during compensation.

Recover after each failpoint and inspect local ledger effects, external financial effects, holds, state, and notification identities. Compare financial outcomes with an explicitly successful reference flow. An additional retry in the audit trail is an acceptable difference.

In-memory fakes can verify whether recovery queries the original transaction or reuses its key. Disk commits, process termination, and worker takeover require integration or system tests using real storage and separate processes or instances. Catching an exception and continuing with the same object does not establish those guarantees.

### Simulate external success with a lost response

Call the real workflow code and replace only external boundaries. The fake provider must record an accepted payment before raising a timeout. Raising an exception without any external effect does not exercise this failure mode.

Pseudocode; adapt the illustrative names to project interfaces:

```text
Provider: accept payment K1, create provider_tx, then lose the response
Execute the real withdraw(K1)
Assert: the flow enters the project's unknown-outcome or pending-recovery state
Assert: the timeout does not cause a blind release as if failure were certain

Provider query for K1: return the original provider_tx as successful
Execute the real resume(K1)
Assert: complete local funds settlement once and resolve the hold as specified
Execute resume(K1) again
Assert: no additional changes to balance, holds, or this transaction's posted amount
Assert: the provider has one financial payment, consistently associated with K1
```

Provider request counts may exceed one. If the fake supports retries with the same key, it must implement the actual provider's deduplication contract and retain inspectable operation records. A mock expectation of "called once" does not prove a unique payment. Use separate fixtures for definite rejection, not-yet-sent requests, and unknown outcomes rather than one vague "call failed" branch.

Check state properties at externally observable or transaction commit boundaries. Do not require a balanced complete ledger while assembling an uncommitted group; do not inspect only the final balance and miss an invalid debit visible between steps.
