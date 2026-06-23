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
- Misc 杂项走本仓库的 [`Misc.list`](./Misc.list)（Twitter/X、Meta 社交、TikTok、Discord、Reddit、Line、Twitch、Pixiv、Wikipedia、GitHub、Speedtest 等），统一走 `Misc` 组
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
- [`Misc.list`](./Misc.list)：杂项分流合集，被 `surfboard.ini` 通过 raw URL 引用进 `Misc` 组。收纳 Twitter/X、Meta 社交（IG/Threads/FB/Messenger/WhatsApp）、TikTok、Discord、Reddit、Line、Twitch、Pixiv、Wikipedia、GitHub、Speedtest 等无独立合集的服务，全部共用 `Misc` 组的节点。后续零散规则也可往这里加
- `Global.list` / `global-fix.list`：早期为 Loon 维护的规则集，保留作历史参考，目前未被 `surfboard.ini` 直接引用

## Clash / Mihomo 配置（clash-verge / clash-meta）

除了 Surfboard，本仓库还维护两份 Mihomo（Clash Meta）配置，分别面向两类客户端：

- [`clash-verge.yaml`](./clash-verge.yaml)：桌面端 **Clash Verge Rev**。多了 `find-process-mode: strict`（按进程名分流）和一个默认关闭的 `tun` 段。
- [`clash-meta.yaml`](./clash-meta.yaml)：**Mihomo 内核** / 移动端（ClashMetaForAndroid、FlClash 等）。

两份配置结构一致，沿用同一套设计：

- **节点** ← `proxy-providers` 从机场订阅拉取
- **规则** ← `rule-providers` 从本公开仓库的 `.list` 拉取（`AI.list` / `Misc.list` + blackmatrix7），两份配置都实时共享
- **主配置永不被机场覆盖**

### 订阅 token 不进公开仓库 —— 用 secret gist 托管

机场订阅 URL 里带 token，等同于你的付费订阅凭证。本仓库是 **public** 的，所以：

- 仓库里的 `clash-verge.yaml` / `clash-meta.yaml` 是 **脱敏模板**，订阅 URL 是占位符 `https://YOUR-SUB-HOST:PORT/path?token=YOUR_TOKEN`，**不含真实 token**。
- 真实配置（填好 token）放在一个 **secret gist** 里。secret gist 不会被搜索 / 列在你的主页，raw URL 含不可猜的哈希；同时 clash 客户端拉取它**无需任何鉴权**，比私有仓库更省事。
- 规则 `.list` 仍留在本公开仓库（不是机密），gist 里的配置通过 raw URL 引用它们。

> 为什么不直接用私有仓库：私有仓库的 raw 链接需要在 URL 里带会过期的 GitHub token，clash 客户端无法自动续期，反而不可用。secret gist 是“隐蔽 + 免鉴权”的折中。

### 怎么搭

1. 打开 <https://gist.github.com> → 新建 gist，添加两个文件 `clash-verge.yaml`、`clash-meta.yaml`，内容复制本仓库同名文件。
2. 把每份里的 `proxy-providers.airport.url` 占位符换成你的真实订阅 URL。
3. 选择 **Create secret gist**（不要选 public）。
4. 进入 gist，点对应文件的 **Raw** 按钮，复制地址。注意用 **不带 commit 哈希** 的形式才会始终指向最新版本：
   ```
   https://gist.githubusercontent.com/<用户名>/<gist-id>/raw/clash-verge.yaml
   https://gist.githubusercontent.com/<用户名>/<gist-id>/raw/clash-meta.yaml
   ```
5. 在客户端里用对应的 raw URL 作为订阅 / Profile 导入：
   - Clash Verge Rev：Profiles → New → 粘贴 `clash-verge.yaml` 的 raw URL
   - ClashMetaForAndroid / FlClash 等：新建配置 → URL 填 `clash-meta.yaml` 的 raw URL

### 后续改配置

- **改规则**：直接编辑本仓库的 `AI.list` / `Misc.list` 并 push，客户端下次刷新即生效（无需动 gist）。
- **改策略组 / DNS / 节点订阅**：编辑 gist 里的 `clash-*.yaml`；记得把对应改动也同步回本仓库的脱敏模板，方便版本管理。
- **换订阅 / token 泄露**：只需更新 gist 里的 `url` 一行；占位模板在公开仓库里始终不含真实 token。

> 提示：因为 Profile 本身托管在 gist（而非机场），客户端里看不到机场的流量/到期信息（那来自机场订阅响应头）。节点和测速不受影响。
