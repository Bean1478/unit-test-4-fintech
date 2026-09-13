# unit-test-4-fintech

[English](README.md) | [简体中文](README.zh-CN.md)

**面向 fintech 场景的专项单元测试 Skill。**

unit-test-4-fintech 帮助编程 Agent 为金额处理、幂等性、支付、退款和异常恢复补充单元测试。Agent 会沿用项目的语言、测试框架和业务规则，修改现有测试套件，并运行新增和受影响的测试。

测试执行了支付流程，并不意味着已经检查重试是否重复扣款、转换是否丢失最小货币单位，或部分退款是否超过剩余可退金额。这个 Skill 引导 Agent 在常规的正常路径、分支和异常测试之外，补充针对这些行为的断言。

[查看 Skill](SKILL.md) · [运行演示](examples/demo.py)

## 适用场景

| 你的任务 | 请求示例 | Skill 帮助 Agent 补充的测试 |
|---|---|---|
| 为新金融功能编写测试 | “给这个退款服务写单元测试。” | 退款成功与拒绝、累计退款限额、重复请求，以及退款是否入账到正确账户 |
| 业务规则变更后更新测试 | “手续费新增了最低收费和封顶，更新相关测试。” | 阈值、舍入中点、运算顺序，以及适用时的历史规则行为 |
| 补充现有测试套件 | “检查支付模块的测试，补上遗漏的金融业务场景。” | 精度损失、重试冲突、部分结算，以及结果未知后的恢复等相关缺口 |

电商、钱包、计费系统等应用中处理资金的业务逻辑，也适合使用。如果你只要求审查，Agent 会提供基于具体代码的发现和测试建议。

## 能帮助 Agent 测什么

参考文件提供测试输入、预期结果、重试序列，以及模拟服务商超时和写入失败的示例。

| 目标逻辑 | 补充场景 | 资金相关断言 | 参考内容 |
|---|---|---|---|
| 金额解析、存储映射与转换 | 不同币种精度、最小单位、大整数、超出允许精度、序列化 | 在支持的转换范围内准确保留金额、资产和单位；按约定处理无效值 | [金额表示与边界](references/money.md#m-01-representation-and-boundaries) |
| 舍入、手续费与分摊 | 正负数的舍入中点、舍入顺序、最低手续费与封顶、尾差分配 | 手续费和各接收方份额准确；尾差只计入一次 | [舍入](references/money.md#m-02-quantization-and-rounding)、[手续费与分摊](references/money.md#m-03-allocation-fees-and-residuals) |
| 外汇转换 | 报价方向、源币种与目标币种精度、有效期、手续费、输出量化 | 使用选定报价后，资产和转换金额正确 | [资产与外汇](references/money.md#m-04-assets-and-fx) |
| 幂等性与重试 | 相同键和请求内容、请求内容变化、租户范围、状态变化后的重放 | 同一逻辑操作只产生一次资金影响；不同的合法操作仍能分别执行 | [幂等约定](references/flows.md#f-01-idempotency-contracts) |
| 资金冻结、扣款与解冻 | 部分结算、剩余冻结资金释放、重复扣款、旧冻结请求重放 | 每一步之后的账面余额、冻结金额和可用余额正确 | [冻结与状态机](references/flows.md#f-02-holds-and-state-machines) |
| 退款、账务分录与冲正 | 累计退款限额、全额退款后的重试、部分冲正、错误账户或币种 | 收款方正确、分录组借贷平衡、关联原始操作，且不产生重复资金影响 | [账务与冲正](references/flows.md#f-03-ledgers-and-reversals) |
| 支付服务商调用与恢复 | 服务商已受理支付但响应丢失、本地确认失败、重复恢复 | 恢复原交易，只结算一次，并按约定处理冻结资金 | [中断与恢复](references/flows.md#f-04-interruption-and-recovery) |
| Webhook 与消息 | 同一次扣款的重复事件、不同的部分扣款、过期状态事件、消息发布确认丢失 | 每个资金操作只生效一次，同时保留后续合法操作 | [API 与 Webhook](references/boundaries.md#b-02-apis-and-webhooks)、[消息](references/boundaries.md#b-03-outbox-and-messaging) |
| 对账、时间与权限 | 金额或币种不匹配、到期边界、历史费率版本、重试时的权限检查 | 差额计算和规则版本正确；请求被拒绝时不会扣款或入账 | [对账](references/boundaries.md#b-04-reconciliation)、[时间与权限](references/boundaries.md#b-05-time-policies-and-permissions-when-relevant) |

按目标代码选择相关用例。每个示例都注明了前提，使用时应按项目规则调整输入和预期结果。

## Agent 如何补充测试

Agent 会阅读代码和现有测试，找出遗漏的场景，并根据独立计算的预期值补充断言。测试调用被测函数或服务，检查金额、余额和分录。随后运行新增和受影响的测试，说明实际结果以及哪些测试未能运行。

业务规则不清楚时，Agent 会指出需要明确的问题，并继续补充其他用例。如果实现与已确定的规则冲突，则保留失败测试并说明原因。

## 示例：补充重复支付测试

这里的 `Wallet` 代指 demo 中的钱包实现。在项目中，应调用实际被测的支付函数或服务。

**检查单次支付成功：**

```python
wallet = Wallet(balance_minor=10000)
wallet.charge('12.34', exponent=2, key='payment-1')

assert wallet.balance_minor == 8766
assert len(wallet.postings) == 1
```

**补充幂等规则，重复处理同一请求：**

```python
wallet = Wallet(balance_minor=10000)
first = wallet.charge('12.34', exponent=2, key='payment-1')
retry = wallet.charge('12.34', exponent=2, key='payment-1')

assert wallet.balance_minor == 8766  # 即使重试，也只扣除 1234
assert len(wallet.postings) == 1    # 只生成一笔分录
assert retry['posting_id'] == first['posting_id']
```

如果实现缺少幂等检查，第一个测试仍然通过；第二个测试会发现余额变成了 `7532`，即同一个请求扣了两次款。

同样的方法可以扩展到参考文件中的其他序列：可退金额耗尽后重放旧退款、部分扣款后释放剩余冻结金额，或恢复服务商响应丢失的支付。

## 运行演示

随附的 [demo](examples/demo.py) 使用有缺陷和修正后的内存钱包，测试金额转换、HALF_EVEN 舍入和支付重试。仅依赖 Python 3 标准库。在 `unit-test-4-fintech/` 目录中运行：

```bash
python examples/demo.py
```

实际运行输出：

```text
Basic example / buggy code: 1 passed, 0 failed, 0 errors
Fintech examples / buggy code: 1 passed, 3 failed, 0 errors
  FAIL test_currency_exponent
  FAIL test_duplicate_request
  FAIL test_half_even_rounding
Fintech examples / fixed code: 4 passed, 0 failed, 0 errors
Demo reproduced: all three intentional defects were detected.
```

| 故意植入的缺陷 | 单次支付测试 | 补充的资金断言 | 错误结果 → 约定的预期结果 |
|---|---|---|---|
| 忽略币种配置，固定乘以 100 | 通过 | 按配置的精度转换 | `1.234`，exponent=3：`123` → `1234` |
| 应使用 HALF_EVEN 时使用了 HALF_UP | 通过 | 检查舍入中点 | `1.005`，exponent=2：`101` → `100` |
| 相同幂等键再次扣款 | 通过 | 检查重试后的余额和分录数量 | 余额 `7532` → `8766`；两笔分录 → 一笔 |

演示明确约定使用 HALF_EVEN、按配置的精度转换，并且同一个键的重试只产生一次资金影响。只有缺陷版本出现三个预期的测试失败，且修正版本的四个测试全部通过时，脚本才会成功退出。

演示覆盖上述三个场景。目前尚未对比 Agent 使用与不使用 Skill 时生成的测试。

## 单元测试的边界

单元测试可以通过可控依赖检查计算、解析器、映射器、校验器、状态转换和恢复决策。真实数据库精度、并发支出、事务原子性和重启后的持久性，需要集成测试或系统测试验证。[依赖边界](references/boundaries.md#b-01-databases-and-concurrency) 说明了不同测试层级分别适合验证哪些断言。

Agent 会指出需要集成测试验证的问题，并在任务要求时补充相应测试。代码行覆盖率帮助定位未测试的路径，资金相关断言用于检查行为是否符合预期。

## 目录内容

| 文件 | 用途 |
|---|---|
| [README.md](README.md) / [README.zh-CN.md](README.zh-CN.md) | 英文与简体中文使用说明 |
| [SKILL.md](SKILL.md) | Agent 指令与参考文件选择规则 |
| [references/money.md](references/money.md) | 金额表示、舍入、手续费、分摊与外汇用例 |
| [references/flows.md](references/flows.md) | 幂等、冻结、退款、账务与恢复序列 |
| [references/boundaries.md](references/boundaries.md) | 适配器、Webhook、消息、对账、时间和权限的依赖设置与断言 |
| [examples/demo.py](examples/demo.py) | 三个金融逻辑缺陷及其检测测试的可运行演示 |
