# Agreed Forex Backtest Requirements

Recorded from the conversation on 15 October 2026. Where a rule changed, this
document records the latest agreed behavior.

## 1. Purpose

- Backtest the user's strategies and report win rates, trade counts, money gained,
  money lost and net profit for a selected date window.
- Use MT5's available historical price data for the MQL5 calculations.
- Support different pairs or symbols, timeframes and starting balances. GBPUSD,
  M15 and a 10,000 starting balance were the initial example, not fixed strategy
  requirements.
- Keep the strategy's core logic independent of a particular gold symbol or
  timeframe.
- Make candle-based calculations fast. Improving speed must preserve the agreed
  SL and TP rules.

## 2. OUT-pattern rules

These rules describe the OUT-based setups discussed in the conversation.

- Use EMA 9 and EMA 18.
- The strategy and the Forex OUT Points indicator must use the same OUT/IN logic.
- Point 0 must be an OUT point.
- The next consecutive swing points 1, 2 and 3 must all be IN points.
- The complete 0–1–2–3 pattern must form. An OUT point in position 3 does not
  qualify as a completed setup.
- A confirming EMA cross completes point 3.
- Take every valid setup, allowing overlapping trades, including simultaneous
  buys and sells where both directions are enabled.

## 3. Strategy distinctions

### Out Down / Out Up

- Use **Out Down-Up** as the strategy name in the reporting application. Remove
  the separate **Out Down** name from the choices.
- OUT-down setups produce BUY trades, using the upcross that confirms point 3.
- Mirror the strategy for OUT-up setups: SELL trades, using the downcross that
  confirms point 3.
- Both directions run together and may overlap.

### Gold LLP Up Sort

- Take only SELL trades from OUT-up setups whose OUT point 0 is labelled LLP.
- Point 0's label matters; the strategy does not simply enter after any LLP point.
- Other entry, stop, target and candle-handling rules follow the shared agreed
  behavior.

### IN Up-Down

- Include **IN Up-Down** as a separately selectable strategy in the reporting
  application.

### 0 Break / 0 Out

- Keep this existing strategy separately identifiable in reports and comparisons.
- Record its actual strategy version, entry technique, pattern and enabled trade
  direction for each run.

## 4. Entry techniques

The reporting application must distinguish entry techniques instead of treating
their results as the same strategy configuration.

Offer the two current methods below in the entry-technique dropdown. Remove the
obsolete EMA-touch-at-close and EMA-cross-at-close choices.

| Technique | Meaning |
| --- | --- |
| 5 candle entry | After the strategy's relevant EMA cross, take the first candle among candles 1–5 that touches EMA 9 or EMA 18. Enter at the following candle's open. |
| Cross, then next open | Enter at the next candle's open after the relevant confirming EMA cross. |

For the EMA-touch technique:

- Either EMA line qualifies.
- The cross candle is candle 0; the touch window is candles 1–5 after it.
- A touch on candle 5 may enter at the following candle's open.
- Expire the setup if no qualifying touch occurs within the five-candle window.
- Later EMA crosses do not cancel or restart an existing waiting setup.
- Each setup keeps its own waiting window; a newer setup does not replace it.

## 5. Stop loss and take profit

For Out Down / Out Up and Gold LLP, the agreed calculations are:

Definitions:

- `X`: the EMA cross marker value, not the cross candle's closing price.
- `E`: the actual trade entry price.
- `B`: the buffer of `0.00010` in price units.
- `L`: the lowest low from the cross confirming point 2 through the cross
  confirming point 3, inclusive, for a BUY setup.
- `H`: the corresponding highest high for the mirrored SELL setup.

### BUY

```text
D = (X - L) / 2 - B
Initial SL = X - D
R = E - Initial SL
TP = E + 2 × R
```

### SELL

```text
D = (H - X) / 2 + B
Initial SL = X + D
R = Initial SL - E
TP = E - 2 × R
```

- The SELL stop-offset calculation adds the buffer.
- TP is measured from the entry price using twice the entry-to-initial-SL
  distance.
- Move SL to the entry price when the trade reaches 1:1 profit.
- Use the same agreed candle-handling rules across the strategies.
- When a candle touches both the active SL and TP, **SL wins**. This replaces the
  earlier TP-first behavior.

## 6. MT5 arrows and tooltips

- Show trade-start and trade-end arrows.
- Trade-start arrows are blue.
- Make the money won or lost visible in the tooltip.
- Keep tooltips short enough for the important prices to remain visible.
- Use concise fields: result, Entry, Exit, Init SL, Fin SL, TP and date.
- Remove the redundant Price field: it repeated the entry or exit price depending
  on the arrow.
- Remove script names, `(net)`, currency suffixes such as `USD`, and other filler
  from the compact tooltip.

## 7. Reporting application

- Maintain a separate repository on the Desktop named **forex backtest**.
- Use a simple Django server with HTML and an intuitive filtering interface.
- Store the results in a database and provide CSV export.
- Keep the data structured so that individual trades belong to an identifiable
  backtest run and strategy version.
- Reports must distinguish different entry techniques and date windows.
- Import latest reports separately for each strategy, pair and timeframe so that
  a newer report for one market does not exclude another market's results. Keep
  each entry variant's reports separate.
- Deploy the website on Render's free web service, with the database hosted on
  Supabase. This replaces the earlier Render-only database preference.

### Required report details

| Area | Details |
| --- | --- |
| Strategy | Name and version |
| Market | Pair or symbol and timeframe |
| Dates | Tested date window and individual trade entry/exit dates |
| Entry | Technique, including five-candle EMA-touch/next-open versus cross/next-open |
| Direction | Long, short or both |
| Pattern | IN UP, IN DOWN, OUT UP or OUT DOWN, including combinations where applicable |
| Point 0 type | LLP, HHP and the other point labels |
| Results | Win rate, total trades, wins, losses, break-even trades, total gained, total lost and net profit |
| Trade details | Entry, exit, initial/final SL, TP and money won or lost |

## 8. Point 0 label filtering and the data gap

- Provide a separate point 0 label filter; OUT UP/DOWN and IN UP/DOWN do not
  replace labels such as LLP and HHP.
- Support LLP, HHP, LLF, HLF, LHF and HHF.
- Applying a label filter must recalculate the matching trade count, win rate and
  profit/loss results.
- Carry the label through the MT5 export, database import and CSV export.
- Recover labels from older reports when those reports explicitly contain them.
- Keep omitted historical labels marked **Not recorded** until newly generated
  reports supply the missing information.
- Regenerate the affected MT5 reports and import them to fill labels that were
  absent from the old exports.
