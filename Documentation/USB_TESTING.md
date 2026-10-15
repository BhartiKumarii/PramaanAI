# Testing the Android app on a real phone over USB

This guide runs the whole stack on your laptop and connects a physical Android
phone to it over a USB cable. The phone talks to your local FastAPI server
through `adb reverse`, so it needs no Wi-Fi, no shared LAN and no Render
deployment. All data comes from the local demo seed and is synthetic.

```
 Phone (PramaanAI app)                    Laptop
 http://127.0.0.1:8000  ──USB / adb reverse──▶  FastAPI on :8000
                                                Web dashboard on :5173 (optional)
```

---

## 1. What you need

| Item | Notes |
|------|-------|
| Android phone | Android 8.0 (API 26) or newer, with a camera. ARM (every normal phone). |
| USB cable | Must be a **data** cable. Charge-only cables are common and won't work. |
| Android SDK platform-tools | Provides `adb`. Comes with Android Studio, or install `platform-tools` on its own. |
| JDK 17 | Needed by Gradle (Android Studio bundles one). |
| Docker + Docker Compose | Recommended way to run the backend. Python 3 + a venv works too (see step 3b). |
| Node.js 18+ | Only needed if you also want the web dashboard locally. |

Check `adb` is on your PATH:

```bash
adb version
```

If it's not found, add the SDK's `platform-tools` directory, for example
`export PATH="$HOME/Android/Sdk/platform-tools:$PATH"` (Linux),
`~/Library/Android/sdk/platform-tools` (macOS), or
`%LOCALAPPDATA%\Android\Sdk\platform-tools` (Windows).

---

## 2. Prepare the phone

1. **Turn on Developer options:** *Settings → About phone* → tap **Build number**
   seven times. (On some phones it's under *Software information*.)
2. **Turn on USB debugging:** *Settings → System → Developer options →
   USB debugging*.
3. Plug the phone into the laptop. If the phone asks for a USB mode, choose
   **File transfer** (some phones only expose adb in that mode).
4. Accept the **"Allow USB debugging?"** prompt on the phone. Tick *Always allow
   from this computer*.
5. Confirm the laptop sees it:

   ```bash
   adb devices
   ```

   You want one line ending in `device`. See [Troubleshooting](#7-troubleshooting)
   if it says `unauthorized`, `no permissions`, or lists nothing.

---

## 3. Start the backend on the laptop

### 3a. With Docker (recommended)

```bash
cp .env.example .env      # first time only — fill in the secrets as the comments describe
docker compose up --build
```

`docker-entrypoint.sh` applies migrations and seeds the demo posts and accounts
(`raxaul_officer`, `sunauli_officer`, `jaigaon_officer`, `it_admin`, password
`BorderShield123`) every time the container starts.

### 3b. Without Docker

```bash
cp .env.example .env      # set DATABASE_URL to a local Postgres, or sqlite:///./pramaan.db
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
alembic upgrade head
python -m scripts.seed_demo_users
python -m scripts.seed_citizen_registry
python -m scripts.seed_blacklist_registry
python -m scripts.seed_demo_cases
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Check it's up from the laptop:

```bash
curl http://127.0.0.1:8000/health
```

---

## 4. Forward the port over USB

```bash
adb reverse tcp:8000 tcp:8000
adb reverse --list          # should show: tcp:8000 tcp:8000
```

Now `127.0.0.1:8000` **on the phone** reaches port 8000 **on the laptop**.
You can sanity-check it by opening `http://127.0.0.1:8000/health` in the phone's
browser.

> The forward is lost whenever the cable is unplugged, the phone reboots, or the
> adb server restarts. Re-run `adb reverse tcp:8000 tcp:8000` after any of those.

---

## 5. Build and install the app pointed at your laptop

The app's server address is baked in at build time (`API_BASE_URL` in
`android/app/build.gradle.kts`). By default it points at the Render deployment;
override it with `-Ppramaan.apiUrl`:

```bash
cd android
./gradlew installDebug -Ppramaan.apiUrl=http://127.0.0.1:8000/
```

(On Windows use `gradlew.bat`.) `installDebug` builds the APK and installs it on
the connected phone in one step. If you'd rather install manually:

```bash
./gradlew assembleDebug -Ppramaan.apiUrl=http://127.0.0.1:8000/
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

Notes:

- Keep the trailing `/` on the URL — Retrofit requires it.
- The app allows plain HTTP (`usesCleartextTraffic`), so no certificate setup is
  needed for local testing.
- If a Play-Store/Releases build of PramaanAI is already on the phone and the
  install fails with `INSTALL_FAILED_UPDATE_INCOMPATIBLE`, uninstall it first:
  `adb uninstall com.pramaanai.officer`.
- **Android Studio instead of the command line:** add
  `pramaan.apiUrl=http://127.0.0.1:8000/` to `android/gradle.properties`
  (don't commit it), pick your phone in the device dropdown and press **Run**.

Confirm the build is using your laptop: in the app, open **Settings** or the
officer **Profile** — the server line should read `127.0.0.1:8000`.

---

## 6. Test it

1. Log in on the phone as `raxaul_officer` / `BorderShield123`.
2. The connectivity indicator should show **Online**.
3. Tap **Verify document**, photograph a document, take a live photo, and read
   the result. Choose **Clear** or **Send to admin**.
4. Watch the requests arrive in the `docker compose` / `uvicorn` terminal.

**Offline → sync check:** unplug the cable (or run `adb reverse --remove-all`)
mid-flow. The app should show **Offline** and queue the case locally. Plug back
in, re-run `adb reverse tcp:8000 tcp:8000`, and the queued case syncs on its
own.

### Optional: the web dashboard on the laptop

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173` and log in as `it_admin` / `BorderShield123`. The
Vite dev server proxies `/api` to `127.0.0.1:8000`, so it uses the same local
backend as the phone — cases you send to admin from the phone appear here, and
replies show up back in the app.

### Useful while testing

```bash
adb logcat --pid=$(adb shell pidof -s com.pramaanai.officer)   # app logs only
adb exec-out screencap -p > screen.png                            # screenshot
```

---

## 7. Troubleshooting

| Symptom | Fix |
|---------|-----|
| `adb devices` lists nothing | Try another cable (likely charge-only) or port; set USB mode to *File transfer*; re-toggle USB debugging. On Windows, install the phone maker's USB driver (or Google USB Driver). |
| `unauthorized` | Unlock the phone and accept the *Allow USB debugging* prompt. If it never appears: *Developer options → Revoke USB debugging authorizations*, then `adb kill-server && adb start-server` and replug. |
| `no permissions (user in plugdev group…)` (Linux) | Add a udev rule for the phone's vendor ID and add yourself to `plugdev`, or as a quick test run `sudo adb kill-server && sudo adb start-server`. |
| App shows **Offline** though the server is running | Re-run `adb reverse tcp:8000 tcp:8000` (it doesn't survive replugging). Check `curl http://127.0.0.1:8000/health` on the laptop. |
| Settings still shows the Render URL | The APK was built without `-Ppramaan.apiUrl`. Rebuild with it — the URL is fixed at build time. |
| `INSTALL_FAILED_UPDATE_INCOMPATIBLE` | A differently-signed copy is installed: `adb uninstall com.pramaanai.officer`, then install again. |
| `INSTALL_FAILED_NO_MATCHING_ABIS` | You're installing on an x86 emulator. Build with `-Ppramaan.emulatorAbis=true` as well. |
| Login fails with a network error but `/health` works | Make sure the seed scripts ran (Docker does this on start; without Docker run the four `scripts.seed_*` commands in step 3b). |
| First verification is slow | The server loads its OCR/face models on first use. Later requests are faster. |

### Alternative: same Wi-Fi instead of USB

If the cable is unavailable, put the phone and laptop on the same Wi-Fi, find the
laptop's LAN IP (`ip addr` / `ipconfig`), make sure the server listens on
`0.0.0.0` and port 8000 isn't firewalled, and build with
`-Ppramaan.apiUrl=http://<laptop-ip>:8000/`. USB with `adb reverse` is more
reliable because it doesn't depend on the network or firewall.
