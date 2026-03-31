# NAS Mount Setup — ignition-primary & ignition-standby

NAS IP: `10.250.2.10`
Share: `Ride Data`
Mount point (both servers): `/mnt/nas_sfgr`
User: `ignition-svc` (read/write — needed for Ignition backups)

---

## On each server (repeat for ignition-primary AND ignition-standby)

### 1. Install cifs-utils (if not already present)
```bash
sudo apt-get install -y cifs-utils
```

### 2. Create the mount point
```bash
sudo mkdir -p /mnt/nas_sfgr
```

### 3. Store credentials securely
```bash
sudo nano /etc/nas_sfgr_credentials
```
File contents:
```
username=ignition-svc
password=YOUR_PASSWORD_HERE
domain=WORKGROUP
```
Lock it down:
```bash
sudo chmod 600 /etc/nas_sfgr_credentials
sudo chown root:root /etc/nas_sfgr_credentials
```

### 4. Add to /etc/fstab for persistent mount
```bash
sudo nano /etc/fstab
```
Add this line (note: share name has a space — must be escaped as `\040`):
```
//10.250.2.10/Ride\040Data  /mnt/nas_sfgr  cifs  credentials=/etc/nas_sfgr_credentials,uid=ignition,gid=ignition,iocharset=utf8,vers=3.0,file_mode=0664,dir_mode=0775,nofail,x-systemd.automount  0  0
```

> **`nofail`** — server boots normally even if NAS is unreachable.
> **`x-systemd.automount`** — mount deferred until first access, avoids boot delays.
> **`file_mode=0664,dir_mode=0775`** — read/write for Ignition backups.
> **`\040`** — fstab escape for a space in the share name.

### 5. Mount now (without rebooting)
```bash
sudo mount -a
```

### 6. Verify read access
```bash
ls /mnt/nas_sfgr
```

### 7. Verify write access (Ignition backup test)
```bash
sudo -u ignition touch /mnt/nas_sfgr/write_test && echo "Write OK" && sudo -u ignition rm /mnt/nas_sfgr/write_test
```

---

## Expected paths

| Purpose | Path |
|---|---|
| Park calendar CSV | `/mnt/nas_sfgr/park_calendar.csv` |
| Ignition backups | `/mnt/nas_sfgr/ignition-backups/` (configure in Gateway > Backup) |

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `mount error(13): Permission denied` | Check NAS user permissions; verify credentials file |
| `mount error(115): Operation now in progress` | SMB version mismatch — try `vers=2.0` or `vers=2.1` |
| Mount disappears after reboot | Check fstab syntax; ensure `cifs-utils` installed |
| Ignition can't write | Check `file_mode`/`dir_mode` and NAS share permissions for `ignition-svc` |
| Space in share name not mounting | Ensure `\040` escape in fstab (not a literal space) |
