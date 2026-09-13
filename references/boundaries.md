# Unit tests at dependency boundaries

Use B-01 for storage mapping, B-02 for APIs and webhooks, B-03 for messaging, B-04 for reconciliation, and B-05 for time and permissions. Call the mapper, adapter, handler, or business function under test with controlled dependency responses.

## B-01 Databases and concurrency

| Unit tests can verify | Requires real dependencies |
|---|---|
| Persistence mappers preserve amount and currency | Round-trip precision and overflow behavior of actual columns, ORMs, and drivers |
| Business decisions after a uniqueness conflict | Effective unique constraints and scope under simultaneous inserts from multiple connections |
| Reservation decisions follow balance rules | Atomic read-check-write behavior at the target isolation level |
| Transaction interfaces are used as intended | Consistency across commit boundaries for debits, postings, idempotency results, and outbox records |
| Recovery uses saved state | Durability after an actual commit, disconnect, restart, or worker takeover |

Unit tests to add directly:

- Build an independent row fixture from the actual storage protocol. For example, a protocol supporting large integers may return the minor-unit string `9007199254740993`. Call the real mapper and assert the exact integer and currency. Use independent expectations in the write direction too, rather than only a round trip whose errors could cancel out.
- Reject or normalize excess precision, missing currencies, and invalid numbers according to the mapper contract. Do not let a fake automatically repair bad data and hide mapper defects.
- Have a fake repository return an existing record, a uniqueness conflict, or a definite save failure. Verify the service's result, subsequent branch, and financial effects. Be explicit about whether failure occurs before commit; an unknown commit outcome is not a confirmed rollback.

Use the target database and independent transactions to verify the guarantees in the right column.

Cover column scale, integer-digit limits, overflow caused by rounding carry, and differences between application and database rounding. PostgreSQL `numeric(p,s)` can quantize values to the column's scale on write; see the [PostgreSQL numeric documentation](https://www.postgresql.org/docs/current/datatype-numeric.html). Verify the project's database version rather than assuming Decimal guarantees end-to-end precision.

## B-02 APIs and webhooks

| Scenario | Dependency setup | Assertions |
|---|---|---|
| HTTP success with business rejection | Return HTTP 200 and the protocol's rejection status | The adapter decodes a business rejection; the business layer does not mark payment successful |
| Invalid required fields | Missing, null, changed-type, or mismatched amount, asset, or transaction-identity fields | Reject or quarantine according to the protocol without directly posting funds; tolerate unrelated added fields as specified |
| Query lags behind the event | Webhook indicates completion; queries return pending and then completed | Wait or retry according to source-authority rules, with one eventual financial effect |
| Stale state arrives late | Current state is successful; an old pending event arrives | Do not roll back funds state based on stale pending data; legitimate refunds and chargebacks remain separate business events |
| Inbox storage fails | Inject a definite failure before the inbox write | Return a retryable outcome as specified by the receiving protocol; do not claim durable receipt; verify actual durability separately |
| Request outcome is unknown | Provider produces an effect, then times out or returns an uncertain result | Query or recover using the [recovery scenarios](flows.md); do not assume payment definitely did not happen |

### Deduplicate at the financial-operation level

Assume the crediting policy adds each successful capture to the balance. Events E1 and E2 both describe capture C1=`2000`; processing them may increase the balance by only `2000`. A later legitimate partial capture C2=`1000` for the same payment should bring the cumulative increase to `3000`.

Test both directions. Deduplicating only by event ID can duplicate a credit; deduplicating only by payment ID can omit a legitimate partial capture. Obtain the identity combination and support for partial captures from the project contract.

### Signatures and raw bytes

To test the real verifier, use provider test vectors or fixed signatures generated independently. Preserve JSON meaning but change whitespace or bytes: verification should fail for a protocol that signs raw bytes. Also test incorrect keys and the protocol's replay window. Do not generate expected signatures with the same signing code being tested.

Mocking the verifier tests only the handler's verification-success and verification-failure branches. Whether actual HTTP middleware preserves raw bytes requires integration tests.

Authorization tests must include retries and cache-hit paths. An idempotency cache must not bypass account or tenant permissions. Use synthetic or sanitized data; do not copy real credentials, payment-card data, or personal information into fixtures.

## B-03 Outbox and messaging

Drive the real logic with fake publishers, outbox repositories, or consumer dependencies:

| Scenario | Core assertion |
|---|---|
| Publisher definitely did not accept the event and returns failure | Retain pending intent according to the contract; do not mark it delivered |
| Publisher accepted the event, but success was not recorded locally | Recovery may send again using the same event ID; two transmissions are not two new business events |
| Consumer receives a duplicate event | Allow necessary processing retries while applying the financial projection change once |

Assert the event's business-operation ID, amount, and currency. Verify atomic commit or rollback of business writes with outbox records, broker redelivery, and end-to-end recovery in integration or system tests.

## B-04 Reconciliation

Use this section only when the target is reconciliation calculation or matching code. Supply independent datasets for both sides to the real matching function. Cover missing records, duplicates, amount/currency/fee differences, and ordinary settlement delays.

Assume three transactions in one currency with gross amounts `10000/20000/30000` and fees `100/200/300`. The settlement contract is gross minus fees, with no other adjustments. Define the discrepancy as expected receipt minus actual receipt:

| Settlement input | Expected result |
|---|---|
| Matching batch receives `59400` | All three transactions match; discrepancy 0 |
| Same batch receives `59390` | Discrepancy 10, with batch and transaction references retained |
| Same numeric amount in a different currency | Currency mismatch; numeric equality does not establish a match |
| Two equal amounts with different business IDs | Match each by its actual identity; do not merge them as duplicates |

Fixed datasets should also cover one-to-many matching, duplicate rows, and pagination boundaries. Identify duplicates according to the input protocol; do not discard legitimate transactions simply because amounts match. When testing correction decisions, inspect the generated correction or reprocessing instructions and repeated execution behavior. Do not overwrite balances to make reconciliation pass.

Use a controlled clock, specified timezone, and calendar to distinguish records inside and outside settlement windows. Data retrieval completeness, cursor durability, and atomic correction postings require higher-level tests.

## B-05 Time, policies, and permissions (when relevant)

Inject a clock into time-sensitive functions. If a quote is valid only while `now < expires_at`, test a fixed cutoff T:

| now | Expected result |
|---|---|
| T - 1 millisecond | Valid |
| T | Expired |
| T + 1 millisecond | Expired |

Use the project's timestamp precision and inclusive or exclusive interval rules. For daily limits, create operations on both sides of the day boundary in the business timezone and check which window includes them. Concurrent limit accumulation requires integration tests; correct window calculation alone does not prove atomic accumulation.

Distinguish business, effective, booking, and settlement times as required. If a historical transaction is bound to fee schedule v1, replay after configuration changes to v2 should still produce the result required by that binding. Do not let tests depend on the machine's current date or the current global fee schedule. Cover DST, holidays, and reporting-period boundaries only when the relevant business logic uses them.

For authorization or maker-checker logic, test self-approval by the same actor, revoked permissions, changes to amount or recipient after approval, and cache-hit paths. Rejected operations must not create unauthorized payment effects. The audit trail may record rejection attempts as specified; do not require every part of the state to remain unchanged.
