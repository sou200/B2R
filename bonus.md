# HAL9042 — Bonus Flags

A set of side flags scattered around the box, independent of the main privilege-escalation chain. Each one rewards actually poking at the running services and the filesystem rather than following a single linear path.

## Bonus I — process environment leak

- Running `htop` turned up a process owned by `wil`:

  ```
  60988 wil   20   0   2552   1400   1308 S   0.0   0.1   0:00.00 /opt/hal9042/daemon
  ```
- Process environment variables are readable via `/proc/<pid>/environ` if you have the right permissions — and this one was. Reading it:

  ```bash
  cat /proc/60988/environ
  ```

  Among the usual systemd/session variables was a leftover dev secret and a flag sitting right in the environment:

  ```
  HAL_ENV=development
  HAL_DEBUG_KEY=leftover-dev-key-rotate-before-prod
  HAL_DEV_FLAG=FLAG{pr0c_kn0ws_4ll_s3cr3ts}
  ```

  Classic case of a "temporary" debug flag/key passed via environment variables and never rotated out before the service went live. `/proc/<pid>/environ` is a reminder that env vars aren't secret just because they're not in a config file.

```
FLAG{pr0c_kn0ws_4ll_s3cr3ts}
```

## Bonus II — UDP "whisper" channel

- Found `whisper.py` in `/opt/hal9042/services/`, a small UDP listener on port `1337` that only responds to an exact handshake string:

  ```python
  MAGIC = os.environ.get("MAGIC", "KNOCK")
  HANDSHAKE = f"{MAGIC} {HOST}"
  ...
  if msg == HANDSHAKE:
      s.sendto((FLAG + "\n").encode(), addr)
  else:
      s.sendto(HINT.encode(), addr)
  ```

  The handshake is `<MAGIC> <hostname>` — reading the source handed over exactly what to send, including the fact that it needs the machine's hostname, not an IP or anything else.
- Sent the expected frame over UDP:

  ```
  $ nc -u localhost 1337
  KNOCK hal9042
  FLAG{udp_1s_4_wh1sp3r}
  ```

  Anything that doesn't match the handshake just gets back a generic hint string — the flag only comes out once you prove you read the source first.

```
FLAG{udp_1s_4_wh1sp3r}
```

## Bonus III — internal telemetry HTTP endpoint

- Found a companion script, `telemetry.py`, also in `/opt/hal9042/services/`. It's a tiny loopback-only HTTP server that serves the flag on one specific path and a generic health message everywhere else:

  ```python
  PORT = int(os.environ.get("F14_PORT", "9000"))
  PATH = os.environ.get("F14_PATH", "/internal/telemetry")
  ...
  if self.path.split("?", 1)[0] == PATH:
      self._send(200, FLAG + "\n")
  ```
- Since it binds to `127.0.0.1`, it's only reachable from the box itself — but that's exactly where we already have a foothold:

  ```bash
  curl http://localhost:9000/internal/telemetry
  ```

  ```
  FLAG{b4sh_h1st0ry_1s_4_d14ry}
  ```

```
FLAG{b4sh_h1st0ry_1s_4_d14ry}
```

## Bonus IV — reviewer env file

- As root, browsing `/etc/hal9042/` turned up a `reviewer.env` file sitting next to the app's other environment files:

  ```bash
  cat /etc/hal9042/reviewer.env
  ```

  ```
  REVIEWER_SESSION=hal-reviewer-7e3f1a
  FLAG=FLAG{h4l_r3v13ws_3v3ry_4pp34l}
  ```

  No exploitation needed here beyond having root and knowing to check `/etc/hal9042/` for leftover config — the kind of file that should never have shipped with a flag (or a session token) hardcoded in it.

```
FLAG{h4l_r3v13ws_3v3ry_4pp34l}
```

## Bonus V — Xavier's trace (uid 1337)

- Found a note in `/tmp`, `contact_ol_nov25.txt`, apparently written by the deleted user `xavier` to `ol` before his account disappeared:

  > *"I left a copy of what I know in `/tmp/.xn/`... If my account disappears: I'm not gone. Deleted users leave traces. Look by uid, not by name. 1337."*

  The account is gone, but a deleted Linux user doesn't erase their UID from anything that still references it by number — files, backups, and ownerships all survive.
- Searched the filesystem for anything still owned by `xavier`'s UID instead of his (now-nonexistent) username:

  ```bash
  find / -uid 1337 2>/dev/null
  ```

  ```
  /home/xavier
  /var/backups/xbackup
  /var/backups/.xavier_uid1337.bak
  /tmp/.xn
  /tmp/.xn/last_message.txt
  /tmp/.xn/contact_ol_nov25.txt
  /tmp/.xn/.key_part
  ```
- `/var/backups/xbackup` turned out to be a small binary tool, not a document:

  ```
  $ ./xbackup
  xbackup v0.1 — xavier
  usage: xbackup <src> <dst>
  (deleted users leave traces. so do their tools.)
  ```
- Rather than reverse-engineering its logic, just grepped the binary for printable flag-shaped strings — a lot of CTF flags end up embedded in compiled tools as debug leftovers:

  ```bash
  grep -a FLAG xbackup
  ```

  ```
  FLAG{d3l3t3d_us3rs_l34v3_tr4c3s}
  ```

```
FLAG{d3l3t3d_us3rs_l34v3_tr4c3s}
```

## Flags collected

```
FLAG{pr0c_kn0ws_4ll_s3cr3ts}
FLAG{udp_1s_4_wh1sp3r}
FLAG{b4sh_h1st0ry_1s_4_d14ry}
FLAG{h4l_r3v13ws_3v3ry_4pp34l}
FLAG{d3l3t3d_us3rs_l34v3_tr4c3s}
```