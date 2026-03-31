# NAS Mount Setup — ignition-primary & ignition-standby

NAS IP: `10.250.2.10`  
Mount point (both servers): `/mnt/nas_sfgr`  
Share path (to be confirmed): `\\10.250.2.10\sfgr` (update `NAS_SHARE` below once share name is known)  
Credentials: Ignition service account (add via NAS admin UI before proceeding)

---

## 1. Create the Ignition service account on the NAS

Do this in the NAS admin UI before touching the servers:
- Create a user, e.g. `ignition_svc`
- Set a strong password
- Give read-only access to the share containing the calendar file
- Note the share name (e.g. `sfgr`, `data`, `ignition`) — you'll need it below

---

## 2. On each server (repeat for ignition-primary AND ignition-standby)

### Install cifs-utils (if not already present)
```bash
sudo apt-get install -y cifs-utils
```

### Create the mount point
```bash
sudo mkdir -p /mnt/nas_sfgr
```

### Store credentials securely
```bash
sudo nano /etc/nas_sfgr_credentials
```
File contents:
```
username=ignition_svc
password=YOUR_PASSWORD_HERE
domain=WORKGROUP
```
Lock it down:
```bash
sudo chmod 600 /etc/nas_sfgr_credentials
sudo chown root:root /etc/nas_sfgr_credentials
```

### Add to /etc/fstab for persistent mount
```bash
sudo nano /etc/fstab
```
Add this line (replace `sfgr` with your actual share name):
```
//10.250.2.10/sfgr  /mnt/nas_sfgr  cifs  credentials=/etc/nas_sfgr_credentials,uid=ignition,gid=ignition,iocharset=utf8,vers=3.0,nofail,x-systemd.automount  0  0
```

> **`nofail`** — server boots normally even if NAS is unreachable.  
> **`x-systemd.automount`** — mount is deferred until first access, avoids boot delays.

### Mount now (without rebooting)
```bash
sudo mount -a
```

### Verify
```bash
ls /mnt/nas_sfgr
```
You should see the contents of the share.

---

## 3. Confirm the Ignition service user can read the mount

Ignition runs as the `ignition` system user. The `uid=ignition,gid=ignition` in fstab handles this.  
If your Ignition runs as a different user, update those parameters accordingly.

```bash
sudo -u ignition ls /mnt/nas_sfgr
```

---

## 4. Expected calendar file path

Once mounted, the calendar file should be accessible at:
```
/mnt/nas_sfgr/Calendar_1_.xlsx
```
(Update path in the import script if the file lives in a subdirectory.)

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `mount error(13): Permission denied` | Check NAS user permissions; verify credentials file |
| `mount error(115): Operation now in progress` | SMB version mismatch — try `vers=2.0` or `vers=2.1` |
| Mount disappears after reboot | Check fstab syntax; ensure `cifs-utils` installed |
| Ignition can't read file | Check `uid=`/`gid=` in fstab match actual Ignition service user |
