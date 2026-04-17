# loon-rules

Rule lists for [Loon](https://nsloon.com/) and [Clash](https://github.com/Dreamacro/clash) / Clash Meta / Mihomo.

## Loon (`*.list`)

| File             | Description                                        |
| ---------------- | -------------------------------------------------- |
| `AI.list`        | AI services (OpenAI, Claude, Gemini, Grok, ...)    |
| `Global.list`    | Upstream global proxy list                         |
| `global-fix.list`| Large curated domain + IP-CIDR blocklist           |

## Clash (`clash/*.yaml`)

Classical rule-provider YAML files, converted from the Loon lists above.

| File                      | Behavior   | Rules |
| ------------------------- | ---------- | ----- |
| `clash/AI.yaml`           | classical  | ~82   |
| `clash/global-fix.yaml`   | classical  | ~30k  |

### Usage

```yaml
rule-providers:
  ai:
    type: http
    behavior: classical
    url: "https://raw.githubusercontent.com/ensomnia16/loon-rules/main/clash/AI.yaml"
    path: ./ruleset/ai.yaml
    interval: 86400
  global-fix:
    type: http
    behavior: classical
    url: "https://raw.githubusercontent.com/ensomnia16/loon-rules/main/clash/global-fix.yaml"
    path: ./ruleset/global-fix.yaml
    interval: 86400

rules:
  - RULE-SET,ai,AI-Proxy
  - RULE-SET,global-fix,PROXY
  - MATCH,DIRECT
```

> Note: Loon-specific compound rules (`AND`/`OR`/`NOT`) are not emitted because
> stock Clash does not parse them. The AI list approximates the original
> `AND, ((DOMAIN-KEYWORD, ...), (DOMAIN-SUFFIX, ...))` pairs using their
> broader `DOMAIN-SUFFIX` component.
