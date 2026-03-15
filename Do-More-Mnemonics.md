# Do-More BRX — Text Import Instruction Reference

This document covers instruction mnemonics and parameter syntax for the **Do-More BRX PLC platform** (AutomationDirect), specifically as they apply to the **text import format** used by Do-More Designer.

> **Designer version tested:** 2.11.2  
> **Hardware:** BX-DM1E-10ED23-D  
> Syntax marked ✅ has been confirmed working via clean hardware import. Syntax marked ⚠️ has not yet been confirmed in the text import context.

---

## General Text Import Rules

- Programs are delimited by `$PRGRM <n>` and `$PGMEND <n>`
- Each rung is a sequence of instructions with no explicit rung delimiter — a new contact instruction (`STR`, `STRE`, `STRNE`, etc.) starts a new rung
- Inline string literals use **doubled double-quotes** for embedded quotes: `""mac=""` produces `mac=` in the string
- Triple double-quotes `"""text"""` produce a quoted string literal as a parameter value
- Hex constants use `0x` prefix: `0x0`, `0x10`, etc.
- Comments use `//`
- Device definitions go in `#BEGIN DEVICE` / `#END` blocks
- Program declarations go in `#BEGIN MEM_CONFIG` / `#END` blocks
- Element documentation goes in `#BEGIN ELEMENT_DOC` / `#END` blocks

---

## Critical Rung Structure Rules ✅

These rules were confirmed by iterative import testing. Violating them produces "Rung Contains Too Many STR Instructions" or "Illegal Rung" errors.

### Rule 1: STR-family always starts a new rung

`STR`, `STRE`, `STRNE`, `STRN` always begin a **new rung**. They cannot appear mid-rung as series conditions. Use `AND`-family for series conditions:

| Use this... | ...not this, mid-rung |
|---|---|
| `ANDNE SL0.length 0` | `STRNE SL0.length 0` |
| `ANDN C32` | `STRN C32` |
| `ANDN T3.Done` | `STRN T3.Done` |
| `ANDNE D1020 0` | `STRNE D1020 0` |

### Rule 2: Output instructions terminate a rung

`SET`, `RST`, `OUT`, `MOVE`, `STRPRINT`, `TMR`, `MQTTPUB`, `MQTTSUB`, `PING`, `NETTIME` are output-side instructions. **Nothing can follow them in the same rung.** Any subsequent logic must be a new rung starting with a fresh `STR`-family contact.

> ❌ This is illegal — SET followed by STRPRINT in same rung:
> ```
> STRE V1010 2
> ANDN C32
> SET C32
> STRPRINT SS1 ...    ← illegal, SET already ended the rung
> ```

> ✅ Correct — split into separate rungs:
> ```
> STRE V1010 2
> ANDN C32
> SET C32
>
> STRE V1010 2
> AND C32
> STRPRINT SS1 ...
> ```

### Rule 3: STRPRINT and DUPBOOL/POPBOOL cannot coexist in the same rung

If a rung needs to both format a string and branch with DUPBOOL, split them:

> ✅ Correct pattern:
> ```
> // Rung B: build payload
> STRE V1010 2
> AND C32
> STRPRINT SS1 0x4 "..."
>
> // Rung C: publish (branch only, no STRPRINT)
> STRE V1010 2
> AND C32
> DUPBOOL
> ANDE V1001 1
> MQTTPUB @MQTT_DEPT ...
> POPBOOL
> ANDE V1001 2
> MQTTPUB @MQTT_CORP ...
> ```

### Rule 4: SET/RST and DUPBOOL/POPBOOL cannot coexist in the same rung ✅

`SET` and `RST` terminate a rung just like other output instructions. `DUPBOOL` cannot follow them.

> ✅ Correct — split into latch rung + publish rung:
> ```
> // Rung A: update latch
> STRE V1010 2
> AND ST10
> ANDN C40
> SET C40
>
> // Rung B: publish
> STRE V1010 2
> AND ST10
> AND C40
> DUPBOOL
> ANDE V1001 1
> MQTTPUB @MQTT_DEPT ...
> POPBOOL
> ANDE V1001 2
> MQTTPUB @MQTT_CORP ...
> ```

### Rule 5: MQTTPUB SS-register prefix-mode topic suffixes must NOT have a leading slash ✅

When P4 is an SS register (prefix mode), the SS register already ends with `/`. A leading slash on the P5 topic suffix produces an absolute topic that ignores the prefix entirely.

> ✅ Correct:
> ```
> MQTTPUB @MQTT_DEPT 0x11 5000 SS0 "3 0x10 ""health/cpu_errors"" ST10" ...
> // publishes to: Buildings/0000/health/cpu_errors  ✅
> ```

### Rule 6: Never put a fixed literal in P4 AND a topic in P5 for MQTTPUB — they concatenate ✅

> ✅ Correct — use SS register as P4 prefix, short suffix in P5:
> ```
> // SS9 = "bootstrap/" built at first scan via STRPRINT
> MQTTPUB @MQTT_DEPT 0x11 5000 SS9 "3 0x10 ""hello"" SS1" ...
> // publishes to: bootstrap/hello  ✅
> ```

### Rule 7: MQTTSUB P3 must be an SS register — blank and slash-containing literals are invalid ✅

MQTTSUB P3 must be an SS or SL register. Blank `""` is invalid. String literals containing `/` are invalid. Only SS/SL register references are accepted.

### Rule 8: MQTTSUB P3+P4 topic concatenate — same as MQTTPUB ✅ (confirmed v2.37)

**MQTTSUB P3 and P4 topic field concatenate to form the full subscription topic** — exactly like MQTTPUB P4+P5.

> ✅ Correct understanding:
> - P3 = SS register containing the **prefix** (must end with `/` if a suffix follows)
> - P4 topic field = suffix appended to P3
> - Full topic = P3 value + P4 topic value

### Rule 9: MQTTSUB P4 topic field cannot be empty ✅ (confirmed v2.30-v2.34)

The importer validates that the P4 topic field is non-empty. Empty string `""` is rejected with "field cannot be Empty" error.

### Rule 10: MQTTSUB P4 topic field accepts SS register name ✅ (confirmed v2.37)

The P4 topic field accepts an SS register name as the topic value — same pattern as MQTTPUB P5 payload items.

> ✅ Confirmed working pattern for dynamic per-PLC subscription topic:
> ```
> // SS8  = "bootstrap/provision/"  built at ST0
> // SS10 = SerialNum MAC string    built at ST0 via STRPRINT SS10 0x4 "SerialNum"
> MQTTSUB @MQTT_DEPT 0x10 SS8 "3 0x10 SS10 SL0" C23 C13 DST511
> ```

> ⚠️ **Build SS registers at ST0, not ST1**, to guarantee they are populated before MQTTSUB fires on first scan.

### Rule 11: MQTTSUB does NOT support wildcards ✅ (confirmed from official docs)

MQTTSUB does not support `+` or `#` wildcard characters in topics. All subscription topics must be listed explicitly, one entry per topic.

**MQTTSUB capacity (from official docs):**
- Up to **50 subscriptions per MQTTSUB instruction**
- Up to **100 topics per MQTT Client device**, spread across a maximum of **10 active MQTTSUB instructions**
- To subscribe to more than 100 topics, create multiple MQTT Client devices pointing to the same broker

---

## Program / Task Structure

### RUN ✅
Calls a subprogram every scan from within another program.
```
STR ST1
RUN PRG_Network
```

---

## Contacts and Coils

### STR ✅
```
STR C1
```

### STRN ✅
```
STRN T1.Done
TMR T1 10000
```
> ❌ Do NOT use STRN mid-rung — use ANDN instead.

### STRE ✅
```
STRE V1010 0
```

### STRNE ✅
```
STRNE D1000:UB2 250
ANDNE D1000:UB2 15
MOVE 0 V1000
```

### AND / ANDN / ANDE / ANDNE ✅
Series conditions — use these mid-rung instead of STR-family.

### OUT / SET / RST / RSTR ✅
Output coils (terminate rung).
```
OUT C0
SET C16
RST C16
RSTR C20 C21   // max 2 operands, second ID must be >= first
```

---

## Timer Instructions

### TMR ✅
```
TMR T0 10000
```
- `T0.Done` ✅ — valid contact
- `T0.TT` ❌ — not valid in text import
- `T0.Run` ❌ — not valid in text import

---

## Move / Math Instructions

### MOVE ✅
```
MOVE DST18 D1000
MOVE 1 V1000
```
> ❌ Cannot MOVE a string literal — use STRPRINT instead.

### ADDD ❌ / MATH ⚠️
ADDD does not exist. MATH unconfirmed in text import.

---

## Branch Instructions

### DUPBOOL / POPBOOL ✅
```
STR C0
DUPBOOL
ANDE V1001 1
PING @IntEthernet 0x1 184156774 500 DST511 0x0 C1 C2
POPBOOL
ANDE V1001 2
PING @IntEthernet 0x1 168792078 500 DST511 0x0 C1 C2
```
> ❌ Cannot mix STRPRINT or SET/RST with DUPBOOL in same rung.

---

## Network Instructions

### PING ✅
```
PING @IntEthernet 0x1 <ip-dword> 500 DST511 0x0 <ok-bit> <fail-bit>
```
> ❌ `PING @MQTT_DEPT ...` — MQTT device references not valid for PING.

### NETTIME ⚠️
SNTP client — text import syntax unconfirmed.

**Suspected syntax:**
```
NETTIME @IntEthernet D1020 123 5000 C_NtpOK C_NtpErr
```

**IP parameter:** Must be a **D register** containing the server IP as a DWORD. ✅ confirmed — V registers and inline constants are not accepted.

The NTP IP is received via MQTT as a dotted-decimal string (e.g. `"10.250.2.110"`), converted to a DWORD via STR2INT, and stored in a D register (D1020 for primary, D1021 for secondary) before NETTIME is called.

> ❌ Do NOT use a held-ON condition — NETTIME is edge-triggered.
> ❌ `NETTIME @IntEthernet 184156782 ...` — inline constant DWORD not accepted.
> ❌ `NETTIME @IntEthernet V1020 ...` — V register not accepted.

---

## MQTT Instructions

### MQTTPUB ✅

**Parameters:**
| # | Value | Notes |
|---|---|---|
| P1 | `@MQTT_DEPT` | MQTT device reference |
| P2 | `0x11` | Must be `0x11` |
| P3 | `5000` | Timeout ms |
| P4 | SS register | Topic prefix |
| P5 | `"count flags topic payload"` | Payload table |
| P6 | `0x0` | |
| P7 | C bit | OK bit |
| P8 | C bit | Fail bit |
| P9 | `DST511` | Status register |

**Flag values:** `0x10` = no-retain, `0x11` = retain.

```
// SS0 = "Buildings/0000/"  → Buildings/0000/health/cpu_errors
MQTTPUB @MQTT_DEPT 0x11 5000 SS0 "3 0x10 ""health/cpu_errors"" ST10" 0x0 C12 C13 DST511

// SS9 = "bootstrap/"  → bootstrap/hello
MQTTPUB @MQTT_DEPT 0x11 5000 SS9 "3 0x10 ""hello"" SS1" 0x0 C12 C13 DST511
```

### MQTTSUB ✅

**Parameters:**
| # | Value | Notes |
|---|---|---|
| P1 | `@MQTT_DEPT` | MQTT device reference |
| P2 | `0x10` | |
| P3 | SS register | Topic prefix (must end with `/` if suffix follows) |
| P4 | `"count flags topic destination"` | topic field appended to P3; accepts SS register name |
| P5 | C bit | Subscribe-OK bit |
| P6 | C bit | Error bit |
| P7 | `DST511` | Status register |

**Capacity:** 50 subscriptions per instruction, 100 topics per MQTT Client device (max 10 instructions). No wildcard support.

> ✅ **Confirmed pattern — dynamic per-PLC topic using SS register in P4 topic field:**
> ```
> STR ST0
> STRPRINT SS8 0x4 """bootstrap/provision/"""
>
> STR ST0
> STRPRINT SS10 0x4 "SerialNum"
>
> MQTTSUB @MQTT_DEPT 0x10 SS8 "3 0x10 SS10 SL0" C23 C13 DST511
> ```

### MQTT Device Definition ✅
```
#BEGIN DEVICE
 @MQTT_DEPT, 32769, 36, 3, 30, ignition-mosquitto, 184156774, 1883, 4294967295, ignition, RideControl, , 
 @MQTT_CORP, 32770, 36, 3, 30, , 168792078, 1883, 4294967295, ignition, RideControl, , 
#END
```

---

## String Instructions

### STRPRINT ✅
```
STRPRINT SS1 0x4 """mac="" SerialNum "";ip="" FmtInt(DST18, ipaddr) "";scan="" DST0 "";"""
STRPRINT SS8 0x4 """bootstrap/provision/"""
STRPRINT SS9 0x4 """bootstrap/"""
STRPRINT SS10 0x4 "SerialNum"
```
- P2: `0x4` (format flags)
- `FmtInt(reg, ipaddr)` — formats DWORD as dotted-decimal IP ✅
- `SerialNum` — PLC MAC address as string ✅
- ❌ Cannot mix STRPRINT and DUPBOOL in same rung

### STRFIND ✅
**Requires exactly 6 parameters. P6 = find-text (last parameter).**
```
MOVE 0 D2000
STRFIND SL0 0x0 D2000 C25 C26 SS8
```

| # | Value | Notes |
|---|---|---|
| P1 | Source | SL or SS register |
| P2 | `0x0` | Must be hex |
| P3 | D register | Offset — must be user D or V register |
| P4 | C bit | Found bit |
| P5 | C bit | Not-found bit |
| P6 | SS register or literal | Find text — **last** |

### STRSUB ✅
```
MOVE 0 D2000
STRSUB SL0 D2000 0x0 32 SS0
```

| # | Value | Notes |
|---|---|---|
| P1 | Source | SL or SS |
| P2 | D register | Offset — must be D register, not constant |
| P3 | `0x0` | Direction |
| P4 | Count | Chars to extract |
| P5 | Destination | SS register |

### STRCOPY / STRCLEAR ✅
```
STRCOPY SL0 SS0 64
STRCLEAR SL0 1
```

### STR2INT ⚠️
Converts a string to an integer (DWORD). Used to convert dotted-decimal IP strings received via MQTT into DWORD values for storage in D registers, which are then passed to NETTIME.

```
// Suspected syntax — text import syntax unconfirmed:
STR2INT SS5 D1020    // converts "10.250.2.110" → DWORD in D1020
STR2INT SS6 D1021    // converts "10.250.2.210" → DWORD in D1021
```

> ⚠️ Text import syntax unconfirmed. Destination must be a D register (required by NETTIME). Confirm whether STR2INT interprets a dotted-decimal IP string as a network-order DWORD or as a plain integer.

### String Register Types
| Type | Description |
|---|---|
| `SS0`–`SS127` | Short string (64 chars) |
| `SL0`–`SLn` | Long string (256 chars) — use as MQTTSUB receive buffer |
| `SL0.length` ✅ | Valid field |
| `SL0.New` ❌ | Not valid in text import |

---

## System Variables

### Scan Time Registers
| Register | Nickname | Description |
|---|---|---|
| `DST0` | `$ScanCounter` | Scans since STOP→RUN |
| `DST1` | `$ScanTime` | Avg scan time (µs) |
| `DST4` | `$ElapsedTicks` | Last scan time (µs) |

### CPU Status Bits
| Bit | Nickname | Description |
|---|---|---|
| `ST0` | `$FirstScan` | ON for first scan after STOP→RUN |
| `ST1` | `$On` | Always ON |
| `ST10` | `$HasErrors` | Any runtime error |
| `ST13` | `$WatchdogReboot` | Watchdog reboot occurred |
| `ST149` | `$BatteryLow` | Battery low |

### Network Registers
| Register | Description |
|---|---|
| `DST18` | Active IP as DWORD |
| `SerialNum` | PLC MAC address string |
| `DST511` | Network instruction status register |
| `D1000:UB2` | Byte 2 (2nd octet) of DWORD |

---

## IP Address Handling

**Decimal DWORD reference:**
| IP | Decimal DWORD | Description |
|---|---|---|
| 10.250.2.102 | 184156774 | Mosquitto MQTT (Dept) |
| 10.250.2.110 | 184156782 | NTP Primary (Dept) |
| 10.250.2.210 | 184156882 | NTP Secondary (Dept) |
| 10.15.144.14 | 168792078 | Corporate MQTT |

---

## Known Invalid Mnemonics

| Mnemonic | Notes |
|---|---|
| `MQTTCONN` | Does not exist |
| `FINDSTR` | Use `STRFIND` |
| `STRGET` | Use `STRSUB` |
| `ADDD` | Does not exist |
| `T0.TT` / `T0.Run` | Not valid in text import |

---

## Element Documentation Format ✅

> Nickname max 16 characters.

```
#BEGIN ELEMENT_DOC
"C0","FLAGS = REST_READONLY SPARK_DISABLED OPCUA_DISABLED","NickName","","Description"
"V1010","FLAGS = REST_READONLY SPARK_DISABLED OPCUA_DISABLED","MQTT_State","","0=IDLE 1=BOOTSTRAP 2=OPERATIONAL"
"T0","FLAGS = REST_READONLY OPCUA_DISABLED","T_NetStable","","10s stability timer"
#END
```
