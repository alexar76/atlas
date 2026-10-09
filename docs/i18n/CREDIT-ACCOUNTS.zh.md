# ATLAS — 预付额度账户

**语言：** [EN](../CREDIT-ACCOUNTS.md) · [RU](CREDIT-ACCOUNTS.ru.md) · [ES](CREDIT-ACCOUNTS.es.md) · [FR](CREDIT-ACCOUNTS.fr.md) · [ZH](CREDIT-ACCOUNTS.zh.md)

ATLAS 对其付费能力计量（`ATLAS_PAYMENT_ENFORCED=1`）并公布价目表。但很长一段时间，这家店只有货架
没有收银台：免费额度是**所有人**的上限，而 402 只指向某个 Hub 的 payment channel — 这没有用，因为
Hub 自己对 ATLAS 的调用同样落在那个匿名额度上。2026-09-12 实测：四个售卖月度计划的 cite-desk，其
全部客户合计每小时只能跑五次。

**额度账户**就是那个付费入口。它是预付的、由运营方签发、按公布价格逐次扣费、不受免费额度限制，并且
拒绝（refusal）从不计费。

## 抵达付费能力的两条路

| | 免费额度 | 额度账户 |
|---|---|---|
| 如何识别调用方 | `X-AIMarket-Sandbox-Visitor` 或调用方地址 | `X-API-Key: atls_…` |
| 上限 | 每个 `quota_window` 内的 `max_per_caller`（默认每小时 5 次） | 余额 |
| 成本 | 无 | 公布的 `price_per_call_usd` |
| 用尽时 | `402` 附价目表 | `402` 说明余额与所需金额 |
| 适用于 | 试用 ATLAS | 任何转售该答案或依赖它的场景 |

`402` 的写法是为了让调用方脱困，而不只是告知它被卡住了：其中带有 `price_per_call_usd`、一个
`free_allowance` 块（`max`、`used`、`quota_window`、`renews`）、通道开启时的 `credit` 块，以及
`how_to_continue` — 一份按顺序排列的「怎样才行」清单。

无法识别的密钥**不是**错误：调用回落到免费额度，402 的 `credit` 块写明 `recognized: false`，运营方
拿到一条日志。desk 配置里的一个笔误不该看起来像故障 — 但也不该看起来像成功。

## 对买方

发送密钥，并读取这次回答花了你多少钱：

```bash
curl -sD /dev/stderr -X POST https://atlas.modelmarket.dev/ai-market/v2/invoke \
  -H 'X-API-Key: atls_…' -H 'Content-Type: application/json' \
  -d '{"capability_id":"atlas.watchbox.check@v1","input":{"west":-1.0,"south":51.3,"east":0.2,"north":51.6,"layers":["flood"]}}'
```

| 响应头 | 含义 |
|---|---|
| `X-Atlas-Credit-Charged-Usd` | 这次调用的花费。被拒绝时为 `0.000000` |
| `X-Atlas-Credit-Balance-Usd` | 扣费之后还剩多少 |
| `X-Atlas-Credit-Low` | 余额降到 `ATLAS_CREDITS_LOW_BALANCE_USD` 及以下时为 `1` |

它们就附在花掉这笔钱的那次调用的响应上，所以盯住余额不需要任何额外请求。未计费的调用完全没有这些
头：缺失意味着「未扣费」，绝不是「零」。

账户也可以直接查询。对未知密钥和已停用密钥都返回 `404`，因此无法用它来试探哪些密钥存在：

```bash
curl -s https://atlas.modelmarket.dev/ai-market/v2/accounts/me -H 'X-API-Key: atls_…'
```

无人值守运行的买方应把 `X-Atlas-Credit-Low` 当作动手的时刻。等 `402` 到来时，它自己客户的工作已经
失败了。

## 对运营方

```bash
# 签发账户。在开启该通道之前就能用，好让密钥先发到手里。
curl -sX POST https://atlas.modelmarket.dev/ai-market/v2/accounts \
  -H "X-Atlas-Token: $ATLAS_OPERATOR_TOKEN" -H 'Content-Type: application/json' \
  -d '{"label":"acme","grant_usd":25}'        # api_key 只返回一次

# 充值。按 `reference` 幂等：同一张发票不会被入账两次。
curl -sX POST https://atlas.modelmarket.dev/ai-market/v2/accounts/<id>/topup \
  -H "X-Atlas-Token: $ATLAS_OPERATOR_TOKEN" -H 'Content-Type: application/json' \
  -d '{"amount_usd":25,"reference":"inv-1043"}'

# 停用某个账户，但不删除其历史。
curl -sX POST https://atlas.modelmarket.dev/ai-market/v2/accounts/<id>/status \
  -H "X-Atlas-Token: $ATLAS_OPERATOR_TOKEN" -d '{"status":"disabled"}'

# 运营方总共替别人保管着多少钱。
curl -s https://atlas.modelmarket.dev/ai-market/v2/credits/stats \
  -H "X-Atlas-Token: $ATLAS_OPERATOR_TOKEN"
```

只保存密钥的哈希。它在创建时显示一次，无法恢复 — 请重新签发。

| 开关 | 默认 | 作用 |
|---|---|---|
| `ATLAS_PAYMENT_ENFORCED` | 关 | 是否对付费能力计量 |
| `ATLAS_CREDITS_ENABLED` | 关 | 是否接受额度密钥。账户可以更早创建 |
| `ATLAS_CREDITS_DB_PATH` | `data/atlas_credits.db` | 账本。必须落在挂载卷上 |
| `ATLAS_CREDITS_LOW_BALANCE_USD` | `1.00` | 低余额阈值。`0` 表示关闭提醒 |

**顺序很重要。** 请在账户已建立、密钥已交到买方手上**之后**再打开 `ATLAS_CREDITS_ENABLED=1`。反过
来，每个尚未拿到密钥的买方，会恰好在系统开始期待它付费的那一刻退回匿名额度。

余额低于阈值时运营方还会收到日志提醒，每个账户最多十分钟一次。它按剩余调用次数来说，而不只是美元：
真正说明还有多少时间反应的是「大约还能调 7 次」，不是「$0.42」。

## 钱到底是怎么走的

- **先预留，后结算。** 一次调用先 `hold`，交付时 `capture`。先扣后退等于为一次崩溃收费。
- **拒绝从不计费。** 带原因的 `ok: false` 会释放预留。传感器机队冷着不花一分钱。
- **单位不是整分。** 余额以毫分（millicent）记账，所以公布的 $0.02 就精确按 $0.02 扣，不会朝任何一
  方取整。
- **崩掉的请求不会冻住钱。** 超过十分钟的预留会被清扫任务释放，被杀掉的进程不给主人留下成本。
- **账本读不出来就拒绝这次调用。** 这与免费额度计量器刻意的 fail-open 相反：多送一次试用只是舍入误
  差，而交付了却没记账的付费产品，那是别人的钱。
- **临时账本直接拒绝启动。** 如果 `ATLAS_CREDITS_DB_PATH` 撑不过一次重新部署，ATLAS 会停下，而不是
  把预付款收进一个自己马上就要删掉的文件。

预付余额属于**资金托管**：别人的钱放在运营方手里，值多少取决于运营方的信用。它背后既没有链上托管，
也没有自动退款 — 这是这条通道诚实的边界，也正因如此，上面那些账本规则没有商量的余地。

## 谁读什么

manifest 与 402 都会声明这条通道（`credits.enabled`、`key_header`、`account_url`），买方可以自行发
现。cite-desk 家族的 desk 会读取响应头，并在自己的 `/api/public/health` 中以 `supply.credit` 重新
发布，同时标明这份余额属于哪个卖方：一个 desk 从多个卖方采购，ATLAS 侧账户健康并不能证明另一个也有
钱。
