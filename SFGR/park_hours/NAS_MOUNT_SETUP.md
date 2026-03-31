# NAS Mount Setup — ignition-primary & ignition-standby

NAS IP: `10.250.2.10`
Share: `Ride Data`
Mount point (both servers): `/mnt/nas_sfgr`
NAS user: `ignition-svc` (read/write)
Ignition OS service user: **`sftp`** (confirmed via `ps aux`)

> **Note:** ignition-standby has no internet access. Follow the special
> cifs-utils install procedure in Step 1 before continuing on that server.

---

## Step 1 — Install cifs-utils

### ignition-primary (has internet)
```bash
sudo apt-get install -y cifs-utils
```

Then also download the packages for transfer to standby:
```bash
mkdir -p ~/cifs-packages && cd ~/cifs-packages
apt-get download cifs-utils
apt-get download $(apt-cache depends cifs-utils \
  | grep '^\s*Depends' | awk '{print $2}')
```

Copy to ignition-standby over the local network:
```bash
scp ~/cifs-packages/*.deb sftp@ignition-standby:~/cifs-packages/
```

### ignition-standby (no internet — run after SCP above)
```bash
cd ~/cifs-packages
sudo dpkg -i *.deb
# If dependency errors appear, run a second time — ordering resolves itself:
sudo dpkg -i *.deb
```

---

## Steps 2–7 — identical on both servers

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
//10.250.2.10/Ride\040Data  /mnt/nas_sfgr  cifs  credentials=/etc/nas_sfgr_credentials,uid=sftp,gid=sftp,iocharset=utf8,vers=3.0,file_mode=0664,dir_mode=0775,nofail,x-systemd.automount  0  0
```

> **`uid=sftp,gid=sftp`** — Ignition runs as the `sftp` OS user on these servers.
> **`nofail`** — server boots normally even if NAS is unreachable.
> **`x-systemd.automount`** — mount deferred until first access, avoids boot delays.
> **`file_mode=0664,dir_mode=0775`** — read/write for Ignition backups.

### 5. Mount now (without rebooting)
```bash
sudo mount -a
```

### 6. Verify read access
```bash
ls /mnt/nas_sfgr
```

### 7. Verify write access
```bash
sudo -u sftp touch /mnt/nas_sfgr/write_test && echo "Write OK" && sudo -u sftp rm /mnt/nas_sfgr/write_test
```

---

## Expected paths

| Purpose | Path |
|---|---|
| Park calendar | `/mnt/nas_sfgr/Calendar_1_.xlsx` |
| Ignition backups | `/mnt/nas_sfgr/ignition-backups/` (configure in Gateway > Config > Backup/Restore) |

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `mount error(13): Permission denied` | Check NAS share permissions for `ignition-svc`; verify credentials file |
| `mount error(115): Operation now in progress` | SMB version mismatch — try `vers=2.0` or `vers=2.1` |
| Mount disappears after reboot | Check fstab syntax; ensure `cifs-utils` installed |
| Ignition can't write | Confirm `uid=sftp` matches actual service user; check NAS user has write access |
| Space in share name not mounting | Ensure `\040` escape in fstab — not a literal space |
| `dpkg` errors on standby | Run `sudo dpkg -i *.deb` a second time — dependency ordering resolves itself |
