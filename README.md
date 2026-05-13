# QQQ Tier 3 Strategy

Codex Skill for a SPY SMA200 + VIX tiered QQQ/TQQQ allocation monitor with daily Chinese signal reports.

## About

`qqq-tier3-strategy` turns a rules-based QQQ/TQQQ trading framework into a reusable Codex Skill. It uses SPY versus its 200-day moving average to identify market regime, VIX tiers to reduce risk during volatility spikes, and a persisted Schmitt-trigger state file to handle buffer-zone holds.

Suggested GitHub About description:

```text
Codex Skill for a SPY SMA200 + VIX tiered QQQ/TQQQ allocation monitor with daily Chinese signal reports.
```

Suggested topics:

```text
qqq, tqqq, spy, vix, trading-strategy, codex-skill, risk-management
```

Update the live GitHub About metadata with:

```bash
GH_TOKEN=... python3 scripts/update_github_about.py \
  --repo MichaelRochonnn/qqq-tier3-strategy \
  --description "Codex Skill for a SPY SMA200 + VIX tiered QQQ/TQQQ allocation monitor with daily Chinese signal reports." \
  --topics "qqq,tqqq,spy,vix,trading-strategy,codex-skill,risk-management"
```

The token needs repository administration write access because GitHub treats About metadata and topics as repository settings.

## Strategy Logic

The strategy uses SPY as the market-regime signal and trades TQQQ, QQQ, or cash.

Priority order:

1. `VIX >= 60`: all cash.
2. `SPY < SMA200 * 0.97`: bear regime, all cash.
3. `SPY > SMA200 * 1.04`: bull regime, allocate by VIX tier.
4. Buffer band: keep the previous stored state.

Bull-regime VIX tiers:

| VIX range | Allocation |
| --- | --- |
| `< 40` | 100% TQQQ |
| `40 <= VIX < 45` | 75% QQQ + 25% cash |
| `45 <= VIX < 50` | 50% QQQ + 50% cash |
| `50 <= VIX < 60` | 25% QQQ + 75% cash |
| `>= 60` | 100% cash |

## Usage

Run the signal script:

```bash
python3 scripts/qqq_tier3_signal.py
```

Machine-readable output:

```bash
python3 scripts/qqq_tier3_signal.py --format json
```

Preview the signal without updating persisted state:

```bash
python3 scripts/qqq_tier3_signal.py --no-update-state
```

By default, the script stores state at:

```text
~/.hermes/state/qqq-tier3-state.json
```

## Data Sources

The script fetches:

- SPY daily history from Nasdaq, with Yahoo Finance as fallback.
- VIX history from Cboe, with Yahoo Finance as fallback.

## Skill Files

- `SKILL.md`: Codex Skill instructions.
- `scripts/qqq_tier3_signal.py`: executable signal monitor.
- `scripts/update_github_about.py`: GitHub About/Topics updater.
- `references/strategy-rules.md`: strategy rule reference.
- `agents/openai.yaml`: UI metadata for Codex Skill discovery.

## Risk Note

This repository implements a rules-based signal generator. It is not personal financial advice. Leveraged ETFs such as TQQQ can experience large drawdowns, volatility drag, and tracking differences, especially over longer holding periods.
