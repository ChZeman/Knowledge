# Ignition Server Networking

## Overview

Both ignition-primary and ignition-standby have two NICs:

| Interface | Network | Purpose |
|---|---|---|
| `enp6s18` | Department `10.250.0.0/19` | PLCs, MQTT, NAS, primary internet |
| `enxc8a362xxxxxx` | Corporate `10.15.144.0/24` | Corporate VLAN access to Ignition UI |

## Routing policy

- Both NICs have a default route.
- Department network uses **metric 100** (preferred for internet).
- Corporate network uses **metric 200** (fallback if department internet is down).
- Corporate VLAN clients connect to Ignition via the corporate NIC (`10.15.144.x`) regardless of which default route is active — traffic to those clients is routed via the directly connected corporate subnet.

## Server addresses

| Server | Department IP | Corporate IP |
|---|---|---|
| ignition-primary | 10.250.2.101 | 10.15.144.11 |
| ignition-standby | 10.250.2.201 | 10.15.144.12 |

## Netplan configs

- `ignition-primary-netplan.yaml` — reference config for primary
- `ignition-standby-netplan.yaml` — reference config for standby

To apply on either server:
```bash
sudo cp ignition-<node>-netplan.yaml /etc/netplan/00-installer-config.yaml
sudo netplan try    # 120s auto-revert if connectivity is lost
sudo netplan apply  # confirm if try succeeds
```

## Verify routing
```bash
ip route
# Should show two default routes with different metrics:
# default via 10.250.0.1 dev enp6s18 proto static metric 100
# default via 10.15.144.1 dev enxc8a362xxxxxx proto static metric 200
```
