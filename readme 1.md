Ran command: `ssh root@76.13.242.106`

The decision to design the system with a strict **1-contract limit** was made for three primary reasons:

---

### **1. The "Sandbox" Safety Principle (Sandbox Testing)**
When deploying an autonomous AI trading bot connected to a real broker account (like Interactive Brokers), the absolute first rule of engineering is **minimum capital exposure**.
* **Glitch Protection:** If there is a software bug (such as an infinite loop sending duplicate orders or a calculation error), trading exactly 1 contract limits the financial risk to the absolute minimum. 
* Once the state machine logic is audited and proven to run flawlessly over many weeks without human intervention, the contract size can be safely increased.

---

### **2. Zero Leverage Risk (Black Swan Protection)**
A key rule of the Wheel strategy is to remain **100% Cash-Secured** to prevent margin calls.
* **Capital Buffer:** Selling 1 contract of AAPL at a `$285` strike locks up `$28,500` in collateral. 
* This leaves **`$221,500` of free cash** in your `$250,000` account. 
* If a "Black Swan" market crash occurs and Apple stock drops 30% overnight, you will be assigned the stock. Because you have a massive cash cushion, there is **zero risk of forced liquidation by the broker**. You can calmly hold the shares and wait for the stock to recover while selling Covered Calls.

---

### **3. Simplifying the State Machine Code**
From a coding standpoint, keeping it to 1 contract allowed us to write a clean, reliable state machine:
* We only have to track a single active position at any given time (e.g., `CSP_ACTIVE` or `CC_ACTIVE`).
* We don't have to manage complex partial fills, scaling in/out, or calculating weighted average costs across multiple different contracts. 

---

### **Summary:**
It was designed this way to **maximize code reliability and capital safety** during the initial live auditing phase. Now that the bot's core loop is proven and hardened, we can easily modify it to support multiple contracts if you wish to scale.