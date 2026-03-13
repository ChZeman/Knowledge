# Do-More BRX — Text Import Instruction Reference

This document covers instruction mnemonics and parameter syntax for the **Do-More BRX PLC platform** (AutomationDirect), specifically as they apply to the **text import format** used by Do-More Designer.

> **Designer version tested:** 2.11.2  
> **Hardware:** BX-DM1E-10ED23-D  
> Syntax marked ✅ has been confirmed working via hardware import. Syntax marked ⚠️ has not yet been confirmed in the text import context.

---

## General Text Import Rules

- Programs are delimited by `$PRGRM <n>` and `$PGMEND <n>`
- Each rung is a sequence of instructions with no explicit rung delimiter — a new contact instruction (`STR`, `STRE`, `STRNE`, etc.) starts a new rung
- Inline string literals use **doubled double-quotes** for embedded quotes: `""mac=""` produces `mac=` in the string
- Triple double-quotes `"""text"""` produce a quoted string literal as a parameter value
- Hex constants use `0x` prefix: `0x0`, `0x1110`, etc.
- Comments use `//`
- Device definitions go in `#BEGIN DEVICE` / `#END` blocks
- Program declarations go in `#BEGIN MEM_CONFIG` / `#END` blocks
- Element documentation goes in `#BEGIN ELEMENT_DOC` / `#END` blocks

---

## Program / Task Structure

### RUN ✅
Calls a subprogram every scan from within another program.
```
STR ST1
RUN PRG_Network
```
- No tasks required for continuous-scan subprograms
- `ST1` = first-scan bit (true on every scan when used as condition)
- Tasks (`ENATASK`, `DISTASK`) are unnecessary when using `RUN` with `ST1`

---

## Contacts and Coils

### STR ✅
Load a normally-open contact (start of rung or parallel branch).
```
STR C1
```

### STRN ✅
Load a normally-closed contact.
```
STRN T3.Done
```

### STRE ✅
Load contact — equal comparison.
```
STRE V1010 0
```

### STRNE ✅
Load contact — not-equal comparison.
```
STRNE V1001 0
```

### AND ✅
Series normally-open contact.
```
AND C1
```

### ANDN ✅
Series normally-closed contact.
```
ANDN C16
```

### ANDE ✅
Series equal comparison.
```
ANDE V1001 1
```

### ANDNE ✅
Series not-equal comparison.
```
ANDNE V1001 0
```

### OUT ✅
Output coil.
```
OUT Y2
```

### SET ✅
Set (latch) a coil.
```
SET C16
```

### RST ✅
Reset (unlatch) a single coil.
```
RST C16
```

### RSTR ✅
Reset a range of coils.
- **Max 2 operands per instruction**
- **Second operand ID must be ≥ first**
```
RSTR C20 C21
RSTR C22 C23
```
> ❌ `RSTR C20 C21 C22 C23` — invalid, too many operands  
> ❌ `RSTR C32 C25` — invalid, second ID must be ≥ first

---

## Timer Instructions

### TMR ✅
On-delay timer. Preset in milliseconds.
```
TMR T0 10000
```

### Timer Status Bits
- `T0.Done` ✅ — valid **only as the first (STR) contact in a rung**
- `T0.TT` ❌ — **not valid** in text import
- `T0.Run` ❌ — **not valid** in text import

> **Important:** `T0.Done` cannot appear after `AND`, after `OUT`, or in `RST`. It must be the sole or first contact in its rung. If you need to act on a timer done state mid-rung, use a helper C bit: `STR T0.Done / SET C_bit`, then use `C_bit` in subsequent logic.

---

## Move / Math Instructions

### MOVE ✅
Copy a value from source to destination.
```
MOVE DST18 D1000
MOVE 1 V1000
MOVE 0 D2000
```
> ❌ `MOVE ""mac="" SS8` — cannot MOVE a string literal into a register; use STRPRINT instead

### ADDD ❌
Not a valid text import instruction. Avoid inline arithmetic — restructure logic to use pre-zeroed registers updated by other instructions.

### MATH ⚠️
Not yet confirmed in text import context.

---

## Branch Instructions

### DUPBOOL / POPBOOL ✅
Fork a rung condition into two parallel branches. Commonly used to send the same condition to two different MQTT device paths.
```
STR C0
DUPBOOL
ANDE V1001 1
PING @IntEthernet 0x1 184156774 500 DST511 0x0 C1 C2
POPBOOL
ANDE V1001 2
PING @IntEthernet 0x1 168792078 500 DST511 0x0 C1 C2
```

---

## Network Instructions

### PING ✅
```
PING @IntEthernet 0x1 <ip-dword> 500 DST511 0x0 <ok-bit> <fail-bit>
```
- P1: `@IntEthernet` — use the Ethernet interface directly
- P3: IP address as a **decimal DWORD** (e.g. `184156774` = 10.250.2.102)
- ❌ `PING @MQTT_DEPT ...` — MQTT device references are not valid for PING

---

## MQTT Instructions

### MQTTPUB ✅
Publish a message to an MQTT broker.
```
MQTTPUB @MQTT_DEPT 0x11 5000 """bootstrap/hello""" "3 0x1110 SerialNum SS1" 0x0 C12 C13 DST511
```

**Parameters:**
| # | Value | Notes |
|---|---|---|
| P1 | `@MQTT_DEPT` | MQTT device reference |
| P2 | `0x11` | **Must be `0x11`, not `0x1`** |
| P3 | `5000` | Timeout in ms |
| P4 | `"""topic"""` or SS register | Inline literal topic, OR SS register used as topic prefix |
| P5 | `"count flags item1 item2"` | Payload table — see below |
| P6 | `0x0` | |
| P7 | C bit | Publish-OK bit |
| P8 | C bit | Publish-fail bit |
| P9 | `DST511` | Status register |

**P5 payload table format:**
- `count` = total items including the flags word
- Confirmed: `"3 0x1110 SerialNum SS1"` (flags + MAC + payload string = 3 items)
- Always include `SerialNum` as item 2 when publishing string payloads

**P4/P5 topic prefix mode:**
When P4 is an SS register, it is treated as an **Optional Topic Prefix**. P5 entries use a suffix string and must set the prefix-use flag bit:
```
MQTTPUB @MQTT_DEPT 0x11 5000 SS0 "3 0x1111 ""/identity/mac"" SS2" 0x0 C12 C13 DST511
```

**P5 flag values (when using SS prefix in P4):**
| Flag | Meaning |
|---|---|
| `0x1111` | Use-prefix + retain + string + if-changed |
| `0x1110` | Use-prefix + no-retain + string + if-changed |

### MQTTSUB ✅
Subscribe to an MQTT topic.
```
MQTTSUB @MQTT_DEPT 0x10 """bootstrap/provision""" "3 0x10 ""bootstrap/provision"" SL0" C23 C13 DST511
```

**Parameters:**
| # | Value | Notes |
|---|---|---|
| P1 | `@MQTT_DEPT` | MQTT device reference |
| P2 | `0x10` | |
| P3 | Topic | Inline literal or SS register |
| P4 | `"count flags topic destination"` | Topic inside P4 uses doubled-quote escaping |
| P5 | C bit | Subscribe-OK bit |
| P6 | C bit | Error bit |
| P7 | `DST511` | Status register |

> ⚠️ Do-More `MQTTSUB` does **not** support wildcard topics. All subscriptions must use static topic strings. For broadcast patterns, all PLCs subscribe to the same topic and filter by payload content.

### MQTT Device Definition ✅
```
#BEGIN DEVICE
 @MQTT_DEPT, 32769, 36, 3, 30, ignition-mosquitto, 184156774, 1883, 4294967295, ignition, RideControl, , 
 @MQTT_CORP, 32770, 36, 3, 30, , 168792078, 1883, 4294967295, ignition, RideControl, , 
#END
```
Field order: `name, type-id, ?, keepalive, timeout, hostname, ip-dword, port, ?, username, password, ?, ?`

---

## String Instructions

### STRPRINT ✅
Format a string into a destination SS register.
```
STRPRINT SS1 0x4 """mac="" SerialNum "";model="" DST27 "";fw="" DST28 "";ip="" D2040 "";"""
STRPRINT SS2 0x4 "FmtInt(D2040, ipaddr)"
STRPRINT SS2 0x4 "FmtBit(X0, val)"
```
- P2: `0x4` (format flags)
- `FmtInt(reg, ipaddr)` — formats a DWORD as dotted-decimal IP string
- `FmtBit(bit, val)` — formats a bit as `0` or `1`
- ❌ Cannot MOVE a string literal into an SS register — use STRPRINT instead

### STRFIND ✅
Search for a substring within a string.
```
MOVE 0 D2000
STRFIND SL0 0x0 D2000 C25 "mac="
```

**Parameters:**
| # | Value | Notes |
|---|---|---|
| P1 | Source string | SL or SS register |
| P2 | `0x0` | Direction — **must be hex (`0x0`), not decimal (`0`)** |
| P3 | `D2000` | In/out offset register — **must be a user D or V register**. DST registers and inline constants are invalid here. |
| P4 | C bit | Set-if-found bit |
| P5 | `"mac="` | Find text — string literal or SS register |

- Max 6 parameters — no set-if-not-found parameter, no case-sensitivity parameter
- Pre-zero the offset register before calling: `MOVE 0 D2000`
- Result: offset register contains position of found text, or -1 if not found
- ❌ DST registers (e.g. DST500) in P3 are treated as constants — do not use
- ❌ Inline constant (e.g. `0x0`) in P3 is invalid

### STRCOPY ✅
Copy characters from one string to another.
```
STRCOPY SL0 SS0 64
```
- P1: Source string
- P2: Destination — **must be an SS register** (❌ D registers invalid)
- P3: Character count
- Max 3 parameters

### STRCLEAR ✅
Clear a string register.
```
STRCLEAR SL0 1
```
- P1: String register to clear
- P2: Count of registers to clear
- ❌ `STRCLEAR SL0` (1 param) — invalid, count is required

### STRSUB ⚠️
Extract a substring. Max 5 parameters. Not yet fully confirmed in text import.
```
STRSUB SL0 D2001 0x0 64 SS0
```
- P1: Source
- P2: Start offset (from STRFIND result register)
- P3: Offset-from flag (`0x0` = from beginning) — must be hex
- P4: Character count
- P5: Destination SS register

### String Register Types
| Type | Description |
|---|---|
| `SS0`–`SS127` | Short string registers |
| `SL0`–`SLn` | Long string registers — used as MQTTSUB receive buffers |
| `SL0.length` ✅ | Valid field — use to check if buffer has received data (`STRNE SL0.length 0`) |
| `SL0.New` ❌ | Not valid in text import |

---

## System Variables

| Variable | Description |
|---|---|
| `ST1` | First-scan bit |
| `DST18` | Active IP address as a 32-bit DWORD |
| `DST27` | PLC model string |
| `DST28` | PLC firmware version string |
| `SerialNum` | PLC MAC address — unique hardware identity |
| `DST511` | General-purpose status/error register for network instructions |
| `D1000:UB2` | Byte 2 (2nd octet) of a DWORD — used for IP network classification |

---

## IP Address Handling

Do-More stores IPs as 32-bit DWORDs.
```
MOVE DST18 D1000       // load active IP
// D1000:UB2 = 2nd octet
```
- `FmtInt(D1000, ipaddr)` in STRPRINT formats as dotted-decimal

**Decimal DWORD reference:**
| IP | Decimal DWORD |
|---|---|
| 10.250.2.102 | 184156774 |
| 10.15.144.14 | 168792078 |

---

## Known Invalid / Non-Existent Mnemonics

| Mnemonic | Notes |
|---|---|
| `MQTTCONN` | Does not exist — MQTT devices connect automatically |
| `FINDSTR` | Wrong name — use `STRFIND` |
| `COMPSTR` | Wrong name — use `STRCMP` (⚠️ unconfirmed) |
| `COPYSTRX` | Wrong name — use `STRCOPY` |
| `STRGET` | Wrong name — use `STRSUB` (⚠️ unconfirmed in text import) |
| `STRSHIFT` | Does not exist |
| `ADDD` | Does not exist as a standalone text import instruction |
| `ENATASK` / `DISTASK` | Valid but unnecessary when using `RUN` from `$Main` |

---

## Element Documentation Format ✅

```
#BEGIN ELEMENT_DOC
"C0","FLAGS = REST_READONLY SPARK_DISABLED OPCUA_DISABLED","NickName","","Description"
"V1010","FLAGS = REST_READONLY SPARK_DISABLED OPCUA_DISABLED","MQTT_State","","0=IDLE 1=BOOTSTRAP 2=OPERATIONAL"
"T0","FLAGS = REST_READONLY OPCUA_DISABLED","T_NetStable","","10s stability timer"
#END
```
