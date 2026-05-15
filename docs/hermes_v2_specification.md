# 🛡️ Hermes V2: Final Institutional Specification

## 1. Allowed States & Split Transitions
The system MUST always exist in one of these four states.

*   **`CASH_ONLY`**: No open positions.
*   **`CSP_ACTIVE`**: Cash Secured Put is open.
*   **`ASSIGNED`**: 100 shares of AAPL held.
*   **`CC_ACTIVE`**: Covered Call is open.

### State Transition Rules (Requires 2-Pulse Persistence)
All transitions involving shares (`ASSIGNED`, `CC_ACTIVE`) require verified portfolio evidence to remain identical across **two consecutive pulses** to account for settlement lag.

1.  **`CASH_ONLY` → `CSP_ACTIVE`**: On successful `SELL_NEW_PUT` execution.
2.  **`CSP_ACTIVE` → `CASH_ONLY`**: On manual `CLOSE` or worthless expiration.
3.  **`CSP_ACTIVE` → `ASSIGNED`**: On 2 consecutive pulses of verified share position (>= 100 shares).
4.  **`ASSIGNED` → `CC_ACTIVE`**: On successful `SELL_NEW_CALL` execution.
5.  **`CC_ACTIVE` → `ASSIGNED`**: If the Call is closed/expires, but 100 shares remain (2-pulse verified).
6.  **`CC_ACTIVE` → `CASH_ONLY`**: If shares are called away (Shares = 0 verified across 2 pulses).

## 2. Universal Validator Rules (The Safety Interlock)
The Executor MUST verify these rules against the `.eye_cache.json` before any trade action.

| Rule | Threshold | Logic | Action if Fails |
| :--- | :--- | :--- | :--- |
| **Delta Gate** | **0.45** | If AI says ROLL but Delta < 0.45 | Block + Alert |
| **DTE Gate (Open)** | **< 1** | If Open Position + DTE < 1 + AI says HOLD | **Attempt Close**, Alert if Fail |
| **DTE Gate (Empty)** | **< 1** | If NO Position + DTE < 1 + AI says OPEN | Block + Alert |
| **Phase Gate** | N/A | If AI says SELL_PUT but State is `ASSIGNED` | Block + Alert |

## 3. Operational Failure & Alerting
*   **Missing Data (API/Network):** Wait 5 minutes and **Retry** (Max 3 attempts).
*   **Validation Failure / Unknown Decision:** 
    1.  **Abort Pulse:** Stop execution immediately.
    2.  **Emergency Alert:** Send Telegram with the **Critical Payload** (see below).
    3.  **Resumption:** The schedule continues next pulse unless a manual stop is performed.

### Critical Alert Payload Requirement:
Every emergency alert MUST contain:
- **Pulse ID**
- **Decision Attempted**
- **Current State**
- **Market Data:** (AAPL Price, VIX, Delta, DTE, Strike)
- **Failure Reason:** (e.g., "Interlock Blocked: Delta 0.24 < 0.45 threshold")

---
*Verified and Finalized for Implementation on 2026-05-15.*
