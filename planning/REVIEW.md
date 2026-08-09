# Review of Changes Since `14550e1`

## Findings

### [P1] Use the SDK's actual snapshot timestamp field

**Location:** `planning/MASSIVE_API.md:121-125` (also reflected in `planning/MARKET_INTERFACE.md:137-146`)

The new reference says that `TickerSnapshot.last_trade` has a `timestamp` field normalized to milliseconds and endorses `snap.last_trade.timestamp / 1000`. That is not the model exposed by the pinned `massive==2.2.0` dependency. `LastTrade.from_dict()` maps the wire-format `t` value to `sip_timestamp`, and it does not convert the nanosecond value or define `timestamp`. Consequently, the existing `massive_client.py:101-110` raises `AttributeError` for every real snapshot, catches it as a malformed snapshot, and never puts Massive prices in the cache. The MagicMock-based tests conceal this by inventing a `timestamp` attribute.

Update the documentation and implementation to read `snap.last_trade.sip_timestamp / 1_000_000_000`, and make the test fixture use a real `LastTrade`/`TickerSnapshot` model (or at least the real field name and nanosecond units) so this API-contract mismatch cannot recur.

### [P1] Do not claim permanent failover is implemented when errors are swallowed

**Location:** `planning/MARKET_INTERFACE.md:152-158` and `planning/MASSIVE_API.md:196-214` (requirement also added at `planning/PLAN.md:137-139,160-167`)

The new documents say any Massive authentication, rate-limit, network, or service failure permanently switches the running app to `SimulatorDataSource`, and `MARKET_INTERFACE.md` says an application lifespan owner performs that switch. No such app/lifespan owner exists in the repository. More importantly, `MassiveDataSource._poll_once()` catches every request exception and returns normally, so even a future owner of the source cannot observe a failure and initiate the documented failover. With an invalid key or an unavailable service, startup completes, the Massive loop retries forever, and the cache remains empty instead of receiving simulated prices.

Either implement an observable failure signal plus the source-swapping owner (and tests for startup and mid-run failure) before calling the market component complete, or clearly label this as future integration work and remove the as-built/permanent-failover claims from the interface and API references.

### [P3] Remove the stale duplicate README

**Location:** `README_old.md:1-55`

This untracked file is a near-copy of the prior README and omits the newly added status warning, so it presents the unbuilt frontend, trading, chat, and Docker workflow as current functionality. Committing both versions creates two conflicting entry-point documents without any reference explaining why the old copy is retained. Delete `README_old.md` (or move genuinely useful historical material under `planning/archive/` with an explicit archival label).

## Validation Notes

- `git diff --check HEAD` passed.
- The pinned dependency was confirmed from `backend/uv.lock` (`massive==2.2.0`), and the timestamp model was checked against the official Massive Python client source.
- The test suite could not be rerun in this environment because the local environment was incomplete and network access was unavailable to fetch locked packages. The review therefore relies on source inspection for the findings above.
