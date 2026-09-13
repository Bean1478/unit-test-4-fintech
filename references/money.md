# Money, conversion, and precision

Use M-01 for representation and conversion, M-02 for rounding, M-03 for fees and allocation, and M-04 for FX. Each example states its assumptions about units, ranges, or rounding. Currency exponents are fixture values; adapt the inputs and expectations to the project's rules.

## M-01 Representation and boundaries

Trace units and types through input text → parser → Money → calculation → persistence mapper → serializer → consumer. Construct expected amounts from decimal strings or exact integers, without passing through binary floating point before creating a Decimal.

| Scenario | Cases and assertions |
|---|---|
| Unit conversion | Fixture exponents 0/2/3/18; `12.34` with exponent=2 becomes `1234`; `1.234` with exponent=3 becomes `1234` |
| Smallest amounts | 0, 1 minor unit, and input below 1 unit; reject or quantize according to the contract rather than silently losing value |
| Large values | Target type limits, limit±1, and intermediate overflow during accumulation or multiplication; cover `2^53-1`, `2^53`, and `2^53+1` on JavaScript paths |
| Invalid input | Missing or nonnumeric values, NaN, Infinity, and excessively long or out-of-range exponents; invalid amounts must not enter financial calculations |
| Text rules | The parser contract determines whether scientific notation, grouping separators, whitespace, leading zeros, and negative zero are accepted |
| Identity | Round-trip the amount with its asset; do not infer a missing currency from a bare number |

A JSON integer is lossless only if the entire consumer chain supports its range. Large integers may need decimal strings. Assert the final consumed value, not just the emitted JSON text. Actual ORM, driver, and column behavior belongs to B-01.

For the valid, exactly representable domain, assert `decode(encode(money)) == money`. Compare amounts and assets according to the contract. Require identical trailing zeros, scale, or text only when representation is part of the protocol. Also use independent known vectors: an encoder and decoder that both mishandle units by a factor of 100 can cancel each other's errors and pass a round-trip test.

Independent conversion vectors:

| Decimal input | Fixture exponent | Integer minor units |
|---|---:|---:|
| `42` | 0 | `42` |
| `12.34` | 2 | `1234` |
| `1.234` | 3 | `1234` |
| `0.000000000000000001` | 18 | `1` |
| `90071992547409.93` | 2 | `9007199254740993` |

Use the last vector only if the project permits that range. Otherwise, assert explicit rejection instead of requiring support. Check these known values independently in the reverse direction rather than having the forward and reverse functions validate each other.

Input `1.234` with exponent=2 cannot be represented losslessly as integer minor units. If the entry-point contract rejects excess precision, assert rejection and no funds movement. If quantization is allowed, check the specified rounding mode. When display formatting permits rounding, check the displayed result and that the original amount remains unchanged; do not require display text to recover all original precision.

## M-02 Quantization and rounding

Establish the target scale, rounding mode, and where rounding occurs. Decimal construction, arithmetic context, division precision, and database quantization can still affect results.

Exact string fixtures, quantized to two decimal places:

| Input | HALF_EVEN | HALF_UP (ties away from zero) |
|---|---|---|
| `1.005` | `1.00` | `1.01` |
| `1.015` | `1.02` | `1.02` |
| `-1.005` | `-1.00` | `-1.01` |

Also test `1.0049` and `1.0051`, on either side of `1.005`. For `-1.239` at two decimal places, truncation toward zero gives `-1.23`, while floor gives `-1.24`. The phrase "round down" alone does not determine the expected result.

Composition example: rounding two amounts of `0.005` individually with HALF_EVEN and then adding gives `0.00`; adding first and rounding afterward gives `0.01`. Test the project's specified operation order rather than assuming the results are equal.

Useful properties include idempotence of the same quantizer and monotonicity under the same configuration without overflow. Derive any error bound first: one nearest-rounding step has an absolute error of at most half a unit; truncation has an absolute error below one unit. Posted amounts should match exactly. Do not hide imbalances behind an arbitrary epsilon.

Parameterized tests should cover both sides of a tie, positive and negative signs, and operation order. Call the project's actual quantization entry point rather than testing only a language or library rounding function; this catches incorrect configuration, premature rounding, and floating-point intermediates.

## M-03 Allocation, fees, and residuals

- Splitting `100` minor units into three equal shares may yield `[34,33,33]` when the contract assigns residuals in stable recipient order. Without a specified order, assert the total, valid shares, and any required determinism.
- Within the same asset and defined account scope, assert `total = sum(allocated shares) + explicitly unallocated residual`. Do not both include a residual in a share and book it again to a residual account.
- Cover totals with fewer minor units than recipients, zero weights, and highly uneven weights. Generate negative totals only when supported. Fairness and independence from input ordering are not universal properties.
- Cover minimum fees, fee caps, and tier thresholds with inputs one unit above and below. Establish basis-point versus percentage units, inclusive versus additional fees, and whether refunds return fees.
- When reversing an original charge, use the original charged amount or allocation records as specified. Do not assume the current fee schedule should be reapplied.

### Fee example: choose inputs that distinguish behavior

Assume positive integer amounts and fees in minor units of the same asset. The rate is `25 bps = 25/10000`. First quantize the proportional fee to an integer with HALF_EVEN, then apply a minimum of `30` and a cap of `500`:

`fee = min(500, max(30, round_half_even(amount_minor × 25 / 10000)))`

| amount_minor | Expected fee_minor | Behavior distinguished |
|---:|---:|---|
| 10000 | 30 | Apply the minimum rather than returning the proportional fee of 25 |
| 12000 | 30 | Proportional fee equals the minimum |
| 12200 | 30 | HALF_EVEN rounds `30.5` to 30 |
| 12201 | 31 | Crossing the rounding tie increases the result |
| 199799 | 499 | Fee remains below the cap |
| 200000 | 500 | Proportional fee equals the cap |
| 240000 | 500 | Apply the cap rather than returning the proportional fee of 600 |

Use these fixed expectations to test the project's fee function directly, also asserting the fee currency and return unit. Do not reproduce the same formula in the test to calculate expected values. Zero amounts, negative refunds, inclusive prices, and tiered pricing need their own contracts; this example does not apply to every fee model.

Quantization can produce the same result for different inputs near a threshold. In addition to "threshold ±1," choose inputs that actually change rounding or min/max output.

### Allocation assertions

Assume a nonnegative integer total split equally, with remaining units assigned one per recipient in stable order: `100 → [34,33,33]`; splitting `2` among five recipients gives `[1,1,0,0,0]`.

Check the total, each recipient's amount, stable residual ownership, and deterministic repeated calculation. A total-only assertion can miss payments to the wrong recipient. Reject invalid inputs such as no recipients or negative weights according to the contract. If a refund must reverse the original allocation, assert reversal against the original records; do not assume reallocating is equivalent.

## M-04 Assets and FX

- Reject arithmetic across different assets according to the contract. A shared symbol does not establish asset identity. Distinguish networks, contracts, and wrapped or bridged assets when relevant.
- Use fixed quotes to test base/quote identity and direction, source and target exponents, fee currency, expiration, quote source, and version.
- Distinguish reference valuation from executed amounts. Retain both original executed legs to test the actual financial result; quote and executed-rate metadata may also be stored.
- Missing, invalid, expired, or mismatched rates must not silently become a 1:1 conversion. If a fallback exists, test its contractually defined selection and labeling.
- FX is not a lossless codec. Do not require `A→B→A` to equal A when spreads, fees, or quantization apply. Calculate expectations independently from both quotes and quantization boundaries. Nor is "value can never increase" a universal property of arbitrary quote combinations.

### FX example: check direction and both units

Assume source asset S has exponent=2 and target asset T has exponent=3. The quote is `1 S = 1.25 T`, there are no fees, and HALF_EVEN integer rounding happens only at the output boundary.

Input `12345` S minor units, or `123.45 S`, produces `154.3125 T` before quantization, and finally **`154312` T minor units**. Assert input and output assets and the integer result. This tie can expose direction errors, a hardcoded factor of 100, premature rounding, and incorrect rounding modes.

Do not invent a reverse quote by taking a reciprocal when one has not been provided. Handle missing, mismatched, and expired quotes according to the project contract without unauthorized financial effects. If the interface returns fee or residual breakdowns, assert their ownership and amounts as well as the net amount.

## Mathematical oracles and generated domains

Generate amounts as bounded integer minor units or decimal strings. Rational numbers can provide an independent model for fees and ratios, with quantization only at contractual boundaries. For operations sensitive to intermediate precision, cover repeated accumulation, large amounts multiplied by small rates, and division with nonterminating decimal results.

Apply properties such as associativity only when the domain is closed, uses the same asset, and has neither rounding nor overflow. Use the project's business formulas as oracles for date-based interest, tax, exchange pricing, and other complex calculations.

Check implementation details against the actual runtime version. See the [official Python decimal documentation](https://docs.python.org/3/library/decimal.html) for context and float-construction behavior. Do not generalize one language's default rounding mode to other libraries.
