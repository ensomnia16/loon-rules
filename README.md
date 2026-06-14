# loon-rules

个人维护的 Surfboard / Surge 规则仓库。核心文件是 [`surfboard.ini`](./surfboard.ini)，作为 [subconverter](https://github.com/tindy2013/subconverter) 的 `&config=` 模板使用。

## 为什么需要这个仓库

机场提供的订阅是 `#!MANAGED-CONFIG` 托管配置，Surfboard 每天会从远端拉取整份配置覆盖本地，导致手动添加的分流规则全部丢失。

通过 subconverter 的 `&config=` 参数注入本仓库的 ini 模板：

- **节点**：仍然来自机场原始订阅，每次更新自动同步
- **策略组 / 规则**：永远来自本仓库的 `surfboard.ini`，机场无法覆盖

## surfboard.ini 做了什么

- 重写了所有策略组：主选择组 `Proxies` + 地区子组（HK/JP/SG/TW/US/Mainland，按节点名 emoji + 中文地名自动筛选）+ 流媒体/应用分流组
- 地区组里 `TW` 和 `Mainland` 已拆开：`TW` 只匹配 🇹🇼/Taiwan/台湾/台北等；🇨🇳/中国/北京/上海等归到 `Mainland`
- 设置 `overwrite_original_rules=true`，丢弃机场默认规则
- AI 服务先引入本仓库的 [`AI.list`](./AI.list)（含 Apple Intelligence、JetBrains AI、Anthropic IP-CIDR 等条目），再追加内联补充域名，统一走 `OpenAI` 组，匹配优先级最高
- Misc 杂项走本仓库的 [`Misc.list`](./Misc.list)（目前收纳 Twitter/X 全家桶），统一走 `Misc` 组
- 流媒体 / 应用走 [blackmatrix7/ios_rule_script](https://github.com/blackmatrix7/ios_rule_script) 的 Surge 列表
- 直连：`Lan.list` + `ChinaMax.list` + `GEOIP,CN`
- 兜底：`FINAL` → `Final` 组（默认走 `Proxies`）

## 订阅 URL 怎么拼

把本 ini 的 raw URL（URL-encode 后）追加到原订阅 URL 的 `&config=` 参数即可：

```
https://api-huacloud.com/sub?target=surfboard&insert=true&emoji=true&tfo=true&udp=true&surge.doh=true&filename=Flower_Trojan&url=<AIRPORT_SUB_URL>&config=https%3A%2F%2Fraw.githubusercontent.com%2Fensomnia16%2Floon-rules%2Fmain%2Fsurfboard.ini
```

> 把 `<AIRPORT_SUB_URL>` 替换成你的机场原始订阅 URL（注意机场 URL 自身也要 URL-encode 一次，避免里面的 `&` `?` 干扰 subconverter 解析）。

## 在 Surfboard 里替换旧订阅

1. 打开 Surfboard → **Profiles**（配置）
2. 找到当前正在使用的 `Flower_Trojan`（或机场默认名）配置
3. 点编辑（笔图标） → 把 **URL** 字段整段替换为上面拼好的新订阅 URL
4. 保存 → 下拉刷新 / 点右上角同步按钮拉取一次
5. 在 **Policy Groups** 里检查策略组是否变成 `Proxies / HK / JP / SG / TW / US / Mainland / OpenAI / Misc / YouTube ...` 等自定义组，确认替换成功

## 后续怎么改规则

1. 直接编辑 `surfboard.ini` 并 push 到 `main` 分支
2. 在 Surfboard 里下拉刷新订阅，新规则即时生效

> Surfboard 默认每 24 小时拉一次托管配置；想立即生效就手动刷新。

## 相关文件

- [`AI.list`](./AI.list)：AI 服务域名合集，被 `surfboard.ini` 通过 raw URL 引用进 `OpenAI` 组。改这里就能调整 AI 分流名单
- [`Misc.list`](./Misc.list)：杂项分流合集，被 `surfboard.ini` 通过 raw URL 引用进 `Misc` 组。目前收纳 Twitter/X 相关域名，后续零散规则也可往这里加
- `Global.list` / `global-fix.list`：早期为 Loon 维护的规则集，保留作历史参考，目前未被 `surfboard.ini` 直接引用
