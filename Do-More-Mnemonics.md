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
| `ANDNE V1021 0` | `STRNE V1021 0` |

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
Load a normally-closed contact (rung start only).
```
STRN T1.Done
TMR T1 10000
```
> ❌ Do NOT use STRN mid-rung — use ANDN instead.

### STRE ✅
Load contact — equal comparison (rung start only).
```
STRE V1010 0
```

### STRNE ✅
Load contact — not-equal comparison (rung start only).
```
STRNE D1000:UB2 250
ANDNE D1000:UB2 15
MOVE 0 V1000
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
ANDN T3.Done
```

### ANDE ✅
Series equal comparison.
```
ANDE V1001 1
```

### ANDNE ✅
Series not-equal comparison.
```
ANDNE SL0.length 0
```

### OUT ✅
Output coil (terminates rung).
```
OUT C0
```

### SET ✅
Set (latch) a coil (terminates rung).
```
SET C16
```

### RST ✅
Reset (unlatch) a single coil (terminates rung).
```
RST C16
```

### RSTR ✅
Reset a range of coils (terminates rung).
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
On-delay timer. Preset in milliseconds (terminates rung).
```
TMR T0 10000
```

### Timer Status Bits
- `T0.Done` ✅ — valid as a contact in any rung position (STR, AND, ANDN, etc.)
- `T0.TT` ❌ — **not valid** in text import
- `T0.Run` ❌ — **not valid** in text import

---

## Move / Math Instructions

### MOVE ✅
Copy a value from source to destination (terminates rung).
```
MOVE DST18 D1000
MOVE 1 V1000
MOVE 0 D2000
```
> ❌ `MOVE ""mac="" SS8` — cannot MOVE a string literal into a register; use STRPRINT instead

### ADDD ❌
Not a valid text import instruction.

### MATH ⚠️
Not yet confirmed in text import context.

---

## Branch Instructions

### DUPBOOL / POPBOOL ✅
Fork a rung condition into two parallel branches.
```
STR C0
DUPBOOL
ANDE V1001 1
PING @IntEthernet 0x1 184156774 500 DST511 0x0 C1 C2
POPBOOL
ANDE V1001 2
PING @IntEthernet 0x1 168792078 500 DST511 0x0 C1 C2
```
> ❌ Cannot mix STRPRINT and DUPBOOL in the same rung — put STRPRINT in its own preceding rung.

---

## Network Instructions

### PING ✅
```
PING @IntEthernet 0x1 <ip-dword> 500 DST511 0x0 <ok-bit> <fail-bit>
```
- P1: `@IntEthernet` — use the Ethernet interface directly
- P3: IP address as a **decimal DWORD** (e.g. `184156774` = 10.250.2.102)
- ❌ `PING @MQTT_DEPT ...` — MQTT device references are not valid for PING

### NETTIME ⚠️
SNTP client — syncs the PLC real-time clock to an NTP server.

> ⚠️ Text import syntax unconfirmed — needs hardware verification before use in production code.

**Behavior:**
- **Edge-triggered** (OFF→ON transition) and **fully asynchronous** — runs to completion even if input goes OFF before it finishes
- Retrieves UTC time from NTP server; applies `$TimeZone` (DST384) and `$SummerTime` (ST768) offsets
- On success sets `$TimeSynced` (ST23)

**Parameters:**
| # | Description | Notes |
|---|---|---|
| P1 | Device | `@IntEthernet` |
| P2 | NTP server IP | Decimal DWORD |
| P3 | UDP port | `123` (standard NTP) |
| P4 | Timeout | ms constant |
| P5 | On Success bit | SET when sync succeeds |
| P6 | On Error bit | SET when sync fails |

**Suspected text import syntax (⚠️ unconfirmed):**
```
NETTIME @IntEthernet 184156782 123 5000 C_NtpOK C_NtpErr
```

**Usage pattern — hourly sync using a timer:**
```
// T_NtpSync fires every 3600000ms (1 hour), edge triggers NETTIME
STRN T_NtpSync.Done
TMR T_NtpSync 3600000

STR T_NtpSync.Done
NETTIME @IntEthernet 184156782 123 5000 C_NtpOK C_NtpErr
```

> ❌ Do NOT use a held-ON condition to trigger NETTIME — it is edge-triggered and requires OFF→ON transition.

---

## MQTT Instructions

### MQTTPUB ✅
Publish a message to an MQTT broker (terminates rung).
```
MQTTPUB @MQTT_DEPT 0x11 5000 """bootstrap/hello/""" "3 0x10 ""bootstrap/hello"" SS1" 0x0 C12 C13 DST511
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

**P5 payload table flag values:**
| Flag | Meaning |
|---|---|
| `0x10` | No-retain, publish on change |
| `0x11` | Retain, publish on change |

**P4/P5 topic prefix mode** (when P4 is an SS register):
```
MQTTPUB @MQTT_DEPT 0x11 5000 SS0 "3 0x11 ""/identity/mac"" SS2" 0x0 C12 C13 DST511
```

### MQTTSUB ✅
Subscribe to an MQTT topic (terminates rung).
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

> ⚠️ Do-More `MQTTSUB` does **not** support wildcard topics. All subscriptions must use static topic strings.

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
Format a string into a destination SS register (terminates rung).
```
STRPRINT SS1 0x4 """mac="" SerialNum "";ip="" D2040 "";"""
STRPRINT SS2 0x4 "FmtInt(D2040, ipaddr)"
STRPRINT SS2 0x4 "FmtBit(X0, val)"
```
- P2: `0x4` (format flags)
- `FmtInt(reg, ipaddr)` — formats a DWORD as dotted-decimal IP string
- `FmtBit(bit, val)` — formats a bit as `0` or `1`
- ❌ Cannot mix STRPRINT and DUPBOOL in the same rung

### STRFIND ✅
Search for a substring within a string. **Requires exactly 6 parameters.**

> ⚠️ **Parameter order:** find-text is the **last** (P6) parameter, NOT P5.

```
MOVE 0 D2000
STRFIND SL0 0x0 D2000 C25 C26 """mac="""
```

**Parameters:**
| # | Value | Notes |
|---|---|---|
| P1 | Source string | SL or SS register |
| P2 | `0x0` | Direction — **must be hex (`0x0`), not decimal (`0`)** |
| P3 | `D2000` | In/out offset register — **must be a user D or V register**. DST registers and inline constants are invalid. |
| P4 | C bit | Set-if-**found** bit |
| P5 | C bit | Set-if-**not**-found bit — **must be a C bit, not a string** |
| P6 | `"""mac="""` | Find text — **string literal (last parameter)** |

> ❌ `STRFIND SL0 0x0 D2000 C25 """mac="""` C26 — wrong order, causes "P5 Set if NOT found: Parameter 5 should not be a string"

- Pre-zero the offset register before calling: `MOVE 0 D2000`
- ❌ DST registers in P3 are treated as constants — do not use
- ❌ Omitting P5 or P6 produces import error

### STRCOPY ✅
Copy characters from one string to another (terminates rung).
```
STRCOPY SL0 SS0 64
```
- P1: Source string
- P2: Destination — **must be an SS register** (❌ D registers invalid)
- P3: Character count

### STRCLEAR ✅
Clear a string register (terminates rung).
```
STRCLEAR SL0 1
```
- P2: Count is **required** — ❌ `STRCLEAR SL0` (1 param) is invalid

### STRSUB ⚠️
Extract a substring. Not yet fully confirmed in text import.
```
STRSUB SL0 D2001 0x0 64 SS0
```

### String Register Types
| Type | Description |
|---|---|
| `SS0`–`SS127` | Short string registers |
| `SL0`–`SLn` | Long string registers — used as MQTTSUB receive buffers |
| `SL0.length` ✅ | Valid field — use to check if buffer has data (`ANDNE SL0.length 0`) |
| `SL0.New` ❌ | Not valid in text import |

---

## System Variables and Named Locations

Source: BRX User Manual, 4th Edition, Appendix D (confirmed from official manual).

### Scan Time Registers
| Register | Nickname | Description |
|---|---|---|
| `DST0` | `$ScanCounter` | Number of scans since last STOP→RUN transition |
| `DST1` | `$ScanTime` | Filtered average scan time in **microseconds** |
| `DST2` | `$MinScanTime` | Shortest scan time since last STOP→RUN (microseconds) |
| `DST3` | `$MaxScanTime` | Longest scan time since last STOP→RUN (microseconds) |
| `DST4` | `$ElapsedTicks` | Last scan time in **microseconds** |

> Note: scan time values are in **microseconds**, not milliseconds. Divide by 1000 for ms.

### CPU / PLC Status Registers
| Register | Nickname | Description |
|---|---|---|
| `DST5` | `$Errors` | Bitmask of all active error flags |
| `DST6` | `$Warnings` | Bitmask of all active warning flags |
| `DST10` | `$PLCMode` | 2=STOP, 3=RUN |
| `DST29` | `$PLCType` | 7 = BRX-DM1E |
| `DST51` | `$FatalTermCode` | Fatal error code (0=none, 1=watchdog/IO/memory, 2=local module not responding, 7=too many modules) |
| `DST53` | `$PLCSubType` | 149 = BX-DM1E-10ED23-D (our hardware) |

### Network Registers
| Register | Nickname | Description |
|---|---|---|
| `DST18` | `$IPAddress` | Active IP as DWORD |
| `DST19` | `$NetMask` | Subnet mask as DWORD |
| `DST20` | `$Gateway` | Gateway IP as DWORD |

### CPU Health Status Bits (ST bits — usable as contacts)
| Bit | Nickname | Description |
|---|---|---|
| `ST1` | `$On` | Always ON — use as unconditional rung enable |
| `ST10` | `$HasErrors` | Any runtime error active |
| `ST11` | `$HasWarnings` | Any runtime warning active |
| `ST13` | `$WatchdogReboot` | Watchdog reboot has occurred |
| `ST14` | `$ModuleFailed` | Any installed module fails validation (ID mismatch) |
| `ST134` | `$InstIOChanged` | I/O module layout changed since last power-on |
| `ST143` | `$DriverError` | Any device reporting a runtime error |
| `ST148` | `$CriticalIOError` | Permanent I/O shutdown — power cycle required |
| `ST149` | `$BatteryLow` | Battery below minimum threshold |

> **Important — per-slot status:** There are NO per-slot DST registers for individual expansion module presence, type, or fault. Module health is reported as aggregate system bits only (`ST14`, `ST134`, `ST148`). Per-slot detail is not accessible via ladder logic DST registers.

### Clock / Time Bits
| Bit | Nickname | Description |
|---|---|---|
| `ST3` | `$1Minute` | 50% duty cycle, 30s ON / 30s OFF |
| `ST4` | `$1Second` | 50% duty cycle, 0.5s ON / 0.5s OFF |
| `ST5` | `$100ms` | 50% duty cycle, 50ms ON / 50ms OFF |

### Other Useful Variables
| Variable | Description |
|---|---|
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

**Decimal DWORD reference:**
| IP | Decimal DWORD | Description |
|---|---|---|
| 10.250.2.102 | 184156774 | Mosquitto MQTT broker (Dept) |
| 10.250.2.110 | 184156782 | NTP Primary (ntp1) |
| 10.250.2.210 | 184156882 | NTP Secondary (ntp2) |
| 10.15.144.14 | 168792078 | Corporate MQTT broker |

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
