# NAS Mount Setup — ignition-primary & ignition-standby

NAS IP: `10.250.2.10`
Share: `Ride Data`
Mount point (both servers): `/mnt/nas_sfgr`
NAS user: `ignition-svc` (read/write)
Ignition OS service user: **`sftp`** (confirmed via `ps aux`)

> **Important:** Do NOT use `x-systemd.automount`. The Ignition gateway Java
> process cannot trigger automount, so the path will appear missing from scripts.
> Use a plain persistent mount instead.

---

## On each server (repeat for ignition-primary AND ignition-standby)

### 1. Install cifs-utils
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
Add this line (share name has a space — escaped as `\040` in fstab):
```
//10.250.2.10/Ride\040Data  /mnt/nas_sfgr  cifs  credentials=/etc/nas_sfgr_credentials,uid=sftp,gid=sftp,iocharset=utf8,vers=3.0,file_mode=0664,dir_mode=0775,nofail  0  0
```

> **`uid=sftp,gid=sftp`** — Ignition runs as the `sftp` OS user on these servers.
> **`nofail`** — server boots normally even if NAS is unreachable.
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

### 7. Verify the gateway (sftp user) can see the park hours file
```bash
sudo -u sftp ls "/mnt/nas_sfgr/Building Monitoring and Control/Park Hours/"
```

---

## Expected paths

| Purpose | Path |
|---|---|
| Park calendar | `/mnt/nas_sfgr/Building Monitoring and Control/Park Hours/Park Hours.xlsx` |
| Ignition backups | Configured separately — NAS share root has a dedicated backups folder |

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `mount error(13): Permission denied` | Check NAS share permissions for `ignition-svc`; verify credentials file |
| `mount error(115): Operation now in progress` | SMB version mismatch — try `vers=2.0` or `vers=2.1` |
| Mount disappears after reboot | Check fstab syntax; ensure `cifs-utils` installed |
| Ignition script shows path not found | Ensure `x-systemd.automount` is NOT in fstab; remount with `sudo umount /mnt/nas_sfgr && sudo mount /mnt/nas_sfgr` |
| Ignition can't write | Confirm `uid=sftp` matches actual service user; check NAS user has write access |
| Space in share name not mounting | Ensure `\040` escape in fstab — not a literal space |
