# Position Mode - Complete Guide

## Overview

**Position Mode** detects parking by monitoring GPS position stability over time. When your vehicle remains in the same location (within tolerance radius) for a configured period, the alarm automatically activates.

This mode is ideal for scenarios where:
- Bluetooth connection is unreliable (distance, interference)
- You want high confidence the vehicle is truly parked
- You need GPS-based detection instead of connection-based

## How It Works

### Detection Flow

1. **GPS Updates Arrive** - Device tracker provides GPS coordinates (via SmartThings polling, typically every 2-10 minutes)
2. **Stability Check** - System checks if position is within `tolerance_radius` of last position
3. **Counter & Timer Logic**:
   - **If position MOVED** (outside tolerance) → Counter resets to 1, Timer **RESTARTS** (10 minutes fresh)
   - **If position STABLE** (within tolerance) → Counter increments, Timer **CONTINUES** running
4. **Timer Expires** - After `stationary_minutes` of continuous stability, timer expires
5. **Final Check** - System verifies `stationary_counter >= stationary_count`
6. **Activation** - If threshold met: save position + activate alarm + send notification

**Key Point:** The timer runs for `stationary_minutes` WITHOUT resetting as long as position stays stable. It only restarts when the vehicle moves outside tolerance.

### Important: GPS Updates vs Webhooks

- **GPS coordinates** come from **device_tracker state changes** (SmartThings polling)
- **Webhooks** only send **manual commands** (start/stop/save), NOT GPS coordinates  
- Webhooks are available for manual control but don't affect Position mode's automatic detection
- Position mode works independently, monitoring GPS stability over time

## Configuration Parameters

### `stationary_minutes` (1-60)

**Time the vehicle must remain stationary before activation.**

- Default: `10` minutes
- Minimum: `1` minute (not recommended - may trigger while at traffic lights)
- Maximum: `60` minutes
- Recommended: `5-15` minutes depending on your use case

**Examples:**
- `5 minutes` - Quick detection, may trigger during brief stops
- `10 minutes` - Balanced, works for most parking scenarios
- `15 minutes` - Very confident, only triggers for long parking

**Note:** Timer runs for `stationary_minutes` and does NOT reset on each GPS update as long as position remains stable. It only restarts when vehicle moves outside tolerance radius.

### `stationary_count` (0-20)

**Number of GPS samples that must be received within tolerance before activation.**

**Special Value: stationary_count=0**
- When set to 0, the counter threshold check is **completely bypassed**
- Timer still runs for `stationary_minutes`
- When timer expires, activation happens **immediately** without checking sample count
- Useful for: testing, slow GPS updates (>10 min intervals), pure time-based detection

- Default: `3` samples
- Minimum: `0` (special bypass mode - see below)
- Maximum: `20` samples
- Recommended: `2-5` depending on GPS update frequency

**Examples with 2-minute GPS updates:**
- `stationary_count=1` - Activates after just 1 stable reading (2 min + timer)
- `stationary_count=3` - Requires 3 stable readings (6 min + timer)
- `stationary_count=5` - Requires 5 stable readings (10 min + timer)

### `tolerance_radius` (meters)

**Maximum distance (in meters) the vehicle can move while still considered "stationary".**

- Default: `200` meters (configurable in options)
- Typical range: `20-100` meters for position mode
- Accounts for GPS drift and minor position variations

## Special Case: stationary_count=0

**When `stationary_count=0`, the count check is bypassed entirely.**

### Behavior
- Timer still runs for `stationary_minutes`
- When timer expires, activation happens **immediately** without checking counter
- Counter still increments on stable positions, but threshold check is skipped
- Useful for testing or when you trust timer alone

### Use Cases
- **Testing** - Verify timer logic without waiting for multiple samples
- **Slow GPS updates** - When device_tracker updates infrequently (>10 min intervals)
- **Simple time-based** - Just "if parked for X minutes, activate"

### Example
```yaml
stationary_minutes: 10
stationary_count: 0  # Bypass counter check
```
Result: After 10 minutes at stable position, activates regardless of sample count.

## Configuration Examples

### Conservative (Recommended)
High confidence, reduces false positives:
```yaml
stationary_minutes: 10  # 10 minute timer
stationary_count: 3     # Requires 3 stable GPS samples
tolerance_radius: 50    # 50 meter tolerance
```
**Timeline:** Position must be stable for 10 minutes with at least 3 GPS updates.

### Aggressive (Fast Detection)
Quick activation, may have false positives:
```yaml
stationary_minutes: 5   # 5 minute timer
stationary_count: 2     # Requires 2 stable samples
tolerance_radius: 75    # 75 meter tolerance (allows more drift)
```
**Timeline:** Position must be stable for 5 minutes with at least 2 GPS updates.

### Time-Only Mode
Ignores sample count, timer-based only:
```yaml
stationary_minutes: 15  # 15 minute timer
stationary_count: 0     # Bypass counter check
tolerance_radius: 50    # 50 meter tolerance
```
**Timeline:** After 15 minutes at stable position, activates immediately.

### Very Conservative
Maximum confidence, for critical scenarios:
```yaml
stationary_minutes: 20  # 20 minute timer
stationary_count: 5     # Requires 5 stable samples
tolerance_radius: 30    # 30 meter tight tolerance
```
**Timeline:** Position must be stable for 20 minutes with at least 5 GPS updates.

## Timer Behavior (Technical Details)

### Critical Fix Applied
**Previous Bug:** Timer reset on every GPS update, preventing it from ever expiring.
**Current Behavior:** Timer runs for `stationary_minutes` and only restarts when vehicle moves outside tolerance.

### How Timer Works Now

**The timer is designed to run for exactly `stationary_minutes` as long as position remains stable:**

1. **First GPS Update (Movement Detected, counter=1)**:
   - Position is new or moved outside tolerance radius
   - Timer **STARTS** - will expire after `stationary_minutes` (e.g., 10 minutes)
   - Counter set to 1

2. **Subsequent GPS Updates While Stable (counter>1)**:
   - Position within tolerance radius of initial position
   - Counter **increments** (2, 3, 4, ...)
   - Timer **CONTINUES** running - does NOT restart
   - GPS updates don't interfere with timer countdown

3. **If Vehicle Moves (counter resets to 1)**:
   - Position moves outside tolerance radius
   - Timer is **CANCELLED and RESTARTED** fresh
   - Counter resets to 1
   - Must wait another full `stationary_minutes`

4. **Timer Expires**:
   - After exactly `stationary_minutes` of stability (e.g., 10 minutes)
   - Checks if `counter >= stationary_count`
   - If yes: Save position + Activate alarm + Send notification
   - If no (stationary_count not reached): Nothing happens, wait for more GPS samples

**Key Insight:** GPS updates every 2 minutes do NOT reset the timer. The timer runs independently for its full duration as long as position stays stable.

### Example Timeline

**Configuration:**
- `stationary_minutes=10`
- `stationary_count=3`
- GPS updates every 2 minutes

**Timeline:**
```
t=0:  Park vehicle → GPS update → counter=1 → Timer START (10 min)
t=2:  Still parked → GPS update → counter=2 → Timer continues (8 min left)
t=4:  Still parked → GPS update → counter=3 → Timer continues (6 min left)
t=6:  Still parked → GPS update → counter=4 → Timer continues (4 min left)
t=8:  Still parked → GPS update → counter=5 → Timer continues (2 min left)
t=10: TIMER EXPIRES → counter(5) >= stationary_count(3) → ✅ ACTIVATE!
```

**If vehicle moves at t=7:**
```
t=7:  Moved >50m → GPS update → counter=1 (reset) → Timer RESTART (10 min)
      Must wait another 10 minutes from t=7 before activation
```

## Choosing the Right Configuration

### Considerations

**GPS Update Frequency:**
- If GPS updates every 2 minutes: `stationary_count=3-5` works well with 10-minute timer
- If GPS updates every 5 minutes: `stationary_count=2-3` works well with 10-minute timer
- If GPS updates every 10+ minutes: Consider `stationary_count=0-2` to avoid long waits

**Use Case:**
- **Daily parking:** `stationary_minutes=5-10`, `stationary_count=2-3`
- **Long-term parking:** `stationary_minutes=15-20`, `stationary_count=5-7`
- **Testing/debugging:** `stationary_minutes=2`, `stationary_count=0`

**False Positive Tolerance:**
- **Low tolerance** (critical security): Higher values, tighter radius
- **High tolerance** (convenience): Lower values, wider radius

### Recommended Starting Points

**Balanced (Most Users):**
```yaml
stationary_minutes: 10
stationary_count: 3
tolerance_radius: 50
```

**Fast (Want quick activation):**
```yaml
stationary_minutes: 5
stationary_count: 2
tolerance_radius: 75
```

**Conservative (Security critical):**
```yaml
stationary_minutes: 15
stationary_count: 5
tolerance_radius: 30
```

## Notifications

When Position mode activates, you receive a notification with:
- Message: "Position stable. Alarm activated."
- Mode: Position
- Map URL: Link to saved coordinates

**Translation Support:**
Notification messages are available in:
- English (en)
- Italian (it)
- French (fr)
- German (de)
- Russian (ru)
- Ukrainian (uk)
- Chinese (zh)

## Troubleshooting

### Alarm Never Activates

**Possible Causes:**
1. **GPS updates too slow** - Timer expires but not enough samples
   - Solution: Lower `stationary_count` or increase `stationary_minutes`
2. **Position drifting** - GPS coordinates vary more than `tolerance_radius`
   - Solution: Increase `tolerance_radius` to 75-100 meters
3. **Vehicle not actually stationary** - Slight movements resetting counter
   - Solution: Check device_tracker history, may need larger radius

### False Positives (Activates While Driving)

**Possible Causes:**
1. **Timer too short** - Activates during traffic stops
   - Solution: Increase `stationary_minutes` to 10-15
2. **Count too low** - Single stable reading triggers activation
   - Solution: Increase `stationary_count` to 3-5
3. **Radius too large** - Slow driving still considered stationary
   - Solution: Decrease `tolerance_radius` to 30-40 meters

### Delays in Activation

**Normal Behavior:**
Position mode requires both:
- Time elapsed (`stationary_minutes`)
- Samples collected (`stationary_count`)

**Expected Delay:**
```
Total wait = stationary_minutes + (sample collection time)
```

Example: 10-minute timer + 3 samples at 2-min intervals = ~10-16 minutes total

**This is by design** - ensures high confidence the vehicle is truly parked.

## Testing Your Configuration

### Test Procedure

1. **Enable Debug Logging:**
   ```yaml
   logger:
     default: info
     logs:
       custom_components.tag_guard_vehicle: debug
   ```

2. **Use Low Values for Testing:**
   ```yaml
   stationary_minutes: 2
   stationary_count: 0  # or 1 for quick test
   ```

3. **Watch Logs:**
   - Monitor device_tracker state changes
   - Watch `stationary_counter` increments
   - Verify timer starts/resets correctly
   - Confirm activation after timer expires

4. **Restore Production Values** after testing

### Debug Information

Check sensor attributes for:
- `stationary_counter` - Current sample count
- `stationary_candidate` - Current candidate position [lat, lon]
- `saved_latitude` / `saved_longitude` - Last saved position
- `alarm_active` - Monitoring status

## Related Modes

### Combined Mode
**Combined Mode** uses **OR logic** — the alarm arms at the FIRST event between:
- Position stable (Position mode criteria)
- Bluetooth disconnected (Connection mode criteria)

It also **disarms on reconnect** (like connection mode). This covers more scenarios:
- Walk away with phone → disconnect triggers immediately
- Leave phone at home → position stable triggers after timer
- Lend vehicle to someone → disconnect (they don't have the tag) triggers immediately

### Connection Mode
Alternative detection via Bluetooth disconnect events — faster but less reliable if connection is spotty. Also disarms on reconnect.

### Manual Mode
Complete manual control — no automatic detection, you trigger activation via webhook or service call.

## Technical Notes

- GPS coordinates come from device_tracker polling, NOT webhooks
- Timer implementation uses `async_call_later()` for async scheduling
- Counter and candidate tracked in coordinator instance state
- Position stability calculated using Haversine formula
- All state persisted to storage, survives HA restarts

## Version History

- **v2.x** - Fixed critical timer reset bug, timer now runs continuously
- **v1.x** - Initial Position mode implementation
