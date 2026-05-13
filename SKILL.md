---
name: qqq-tier3-strategy
description: Compute and explain the QQQ/TQQQ tiered allocation strategy using SPY versus its 200-day SMA, VIX risk tiers, Schmitt trigger buffer-state handling, and cash protection rules. Use when the user asks for QQQ/TQQQ buy strategy, daily allocation reminders, SPY SMA200 regime checks, VIX tier signals, or updates to the QQQ Tier 3 monitor.
---

# QQQ Tier 3 Strategy

## Quick Start

Use `scripts/qqq_tier3_signal.py` to calculate the current allocation from live/recent market data:

```bash
python3 /Users/michaelrochon/.codex/skills/qqq-tier3-strategy/scripts/qqq_tier3_signal.py
```

For machine-readable output:

```bash
python3 /Users/michaelrochon/.codex/skills/qqq-tier3-strategy/scripts/qqq_tier3_signal.py --format json
```

The script uses Nasdaq daily history for SPY and Cboe VIX history for VIX, with Yahoo Finance as a fallback. It computes SPY SMA200 from daily closes and stores Schmitt-trigger state in `~/.hermes/state/qqq-tier3-state.json` unless `--no-update-state` is passed.

## Workflow

1. Run the signal script before giving a daily recommendation.
2. Treat `VIX >= 60` as the highest-priority hard stop: all cash.
3. Update the SPY market regime with Schmitt trigger thresholds:
   - `SPY > SMA200 * 1.04`: bull regime.
   - `SPY < SMA200 * 0.97`: bear regime.
   - Otherwise keep the previous stored regime.
4. In bear regime, recommend all cash.
5. In bull regime, apply VIX tiers:
   - `VIX < 40`: 100% TQQQ.
   - `40 <= VIX < 45`: 75% QQQ, 25% cash.
   - `45 <= VIX < 50`: 50% QQQ, 50% cash.
   - `50 <= VIX < 60`: 25% QQQ, 75% cash.
6. If SPY is inside the buffer and no previous state exists, say the system is waiting for a clean trigger. Default to cash unless the user explicitly confirms an existing position to hold.

## Output Style

For user-facing Chinese reminders, keep the message compact:

- One-line action: today's allocation.
- Key inputs: SPY close, SMA200, SPY/SMA ratio, VIX.
- Trigger explanation: hard stop, bull, bear, or buffer hold.
- State note: whether the stored regime/allocation changed.
- Risk note: this is a rules-based signal, not personal financial advice.

## References

Read `references/strategy-rules.md` when editing the strategy logic, explaining the full rule set, or auditing whether a recommendation matches the user's original specification.
