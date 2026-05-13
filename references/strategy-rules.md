# QQQ Tier 3 Strategy Rules

## Signal System

- Signal asset: SPY, used as the market-regime proxy for the S&P 500.
- Trend indicator: 200-day simple moving average, approximately 40 trading weeks.
- Volatility indicator: VIX.
- Trading assets: TQQQ, QQQ, and cash.

## Schmitt Trigger

- Upper boundary: `SPY > SMA200 * 1.04` means bull regime.
- Lower boundary: `SPY < SMA200 * 0.97` means bear regime and all cash.
- Buffer band: keep the previous regime/allocation.

## Priority Order

1. `VIX >= 60`: all cash as extreme hard-stop protection.
2. `SPY < SMA200 * 0.97`: all cash as bear-market protection.
3. `SPY > SMA200 * 1.04`: apply VIX allocation tiers.
4. Buffer band: keep the previous stored state.

## VIX Tiers In Bull Regime

| VIX range | Allocation |
| --- | --- |
| `< 40` | 100% TQQQ |
| `40 <= VIX < 45` | 75% QQQ + 25% cash |
| `45 <= VIX < 50` | 50% QQQ + 50% cash |
| `50 <= VIX < 60` | 25% QQQ + 75% cash |
| `>= 60` | 100% cash |

## VIX Recovery Rule

When the stored market regime is bull and VIX falls back below 40, return directly to 100% TQQQ.

## State Handling

The buffer band is stateful. A monitor should persist at least:

- Last market regime: `bull`, `bear`, or `unknown`.
- Last allocation.
- Last signal reason.
- Last run timestamp.

If no previous state exists and SPY is inside the buffer, the conservative recommendation is cash / wait for a clean trigger unless the user has supplied an existing position to maintain.
