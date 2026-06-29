# Deploying the server to the cloud (for a real, remote Pi)

For a live race the car's Pi is on cellular and can't share a network with your laptop, so
the server needs a public URL. This guide deploys it to **Render** (free, deploys straight
from GitHub). The same `Procfile` works on Railway/Fly.io too.

> **What gets deployed:** only the **server + portal** (`server/` + `dashboard/`). The SDK
> runs on the Pi; the simulated car is *not* deployed (the cloud shows real Pi data only).

## Caveats on free tiers (read first)

- **Cold starts:** a free service **sleeps after ~15 min idle**; the first request then takes
  ~30–60 s to wake. The SDK simply buffers and retries during that window — **no data is
  lost** — but the portal may show "server unreachable" until it wakes. Hit the URL once a
  minute before recording to keep it warm.
- **Ephemeral database:** the SQLite file resets if the service redeploys/restarts. Fine for
  a single recording session. (For persistence you'd add a Render Postgres or a paid disk —
  out of scope for the seminar.)
- **Open endpoints:** ingestion needs the API key, but read/rules/keys endpoints are
  unauthenticated (local-tool scope, see [../FUTURE_WORK.md](../FUTURE_WORK.md)). A public
  URL is therefore readable by anyone who has it. Acceptable for a short demo; don't put
  anything sensitive on it.

---

## Step 1 — Push the project to GitHub

The repo is already git-initialized and `.gitignore` excludes the reference folders
(`SolarRace_OS/`, `Pit_Dashboard/`), the venv, and `*.db`. Create an empty GitHub repo, then:

```bash
git add -A
git commit -m "Edge-Sync SDK: server, portal, docs"
git branch -M main
git remote add origin https://github.com/<you>/<repo>.git
git push -u origin main
```

## Step 2 — Create the Render service

1. Sign in at <https://render.com> (free; GitHub login is easiest).
2. **New → Blueprint**, pick your repo. Render reads [`render.yaml`](../render.yaml) and
   proposes the web service. (Or **New → Web Service** and set Build =
   `pip install -r requirements.txt`, Start =
   `uvicorn server.main:app --host 0.0.0.0 --port $PORT`.)
3. When prompted for the `TELEMETRY_API_KEY` env var, enter a **strong value you choose**
   (e.g. a long random string) — this is the key the Pi will use. Keep it somewhere.
4. Click **Apply / Create**. First build takes a couple of minutes.

You'll get a public URL like `https://edge-sync-telemetry.onrender.com`.

## Step 3 — Check it

Open the URL in a browser — the **portal** loads. Visit `…/docs` for the API reference.
The chart is empty until the Pi sends data. (The **Setup** tab can also generate keys, but
prefer the env-var key from Step 2 — generated keys don't survive a free-tier restart.)

## Step 4 — Point the Pi at the cloud

On the Raspberry Pi running `SolarRace_OS` (the Pi just needs internet — it does **not** have
to share a network with your laptop, because the server is public):

1. **Put the SDK on the Pi.** Copy the `sdk/` folder into the SolarRace_OS project root — the
   same level as `modules/` and `main.py`, so `import sdk` resolves just like `import modules`
   already does. Install its one dependency:
   ```bash
   pip3 install httpx
   ```
2. **Create `telemetry.json`** in the SolarRace_OS root (next to `main.py`):
   ```json
   {
     "server_url": "https://edge-sync-telemetry.onrender.com",
     "api_key": "<the key you set on Render in Step 2>",
     "device_id": "solar-car-01",
     "network": "lte",
     "metadata": { "fw": "RaceOS-2.0", "type": "solar-car" }
   }
   ```
3. **Edit `main.py`** — three small additions:
   ```python
   # with the other imports at the top:
   import os
   from sdk.client import auto_init
   from sdk.integrations.solar_race import track_vehicle_state

   # in main(), right after initialize_firebase(...):
   auto_init(os.path.join(os.path.dirname(__file__), "telemetry.json"))

   # in _decode_message(), right after push_telemetry_to_cloud(self.vehicle_state):
   track_vehicle_state(self.vehicle_state)
   ```
   (The absolute path means `telemetry.json` is found no matter which folder you launch from.)
4. **Run SolarRace_OS** the way you normally do — live CAN, or its `can_dump.txt` replay mode
   if the car isn't powered. It now sends to the cloud in parallel with its existing push.
   Real BMS / motor / battery-temp values appear on the portal from anywhere.

> Env-var alternative: instead of `telemetry.json` you can `export TELEMETRY_SERVER_URL`,
> `TELEMETRY_API_KEY`, `TELEMETRY_DEVICE_ID`, `TELEMETRY_NETWORK` and call a bare `auto_init()`.
> The config file is steadier across reboots and launch methods.

### Troubleshooting

- **`ModuleNotFoundError: sdk`** — the `sdk/` folder isn't beside `main.py`; move it there.
- **`401` in the Pi logs / no data** — the key doesn't match Render's current `TELEMETRY_API_KEY`.
- **`telemetry.json` not found** — the `os.path.dirname(__file__)` path (Step 3) fixes this;
  confirm the file sits next to `main.py`.
- **Nothing appears, no error** — free-tier server cold-starting (wait ~30–60 s, refresh), or
  the Pi has no internet.

## Step 5 — Record the video

- Open the portal URL on your laptop; show real data arriving on **Overview**, device health
  on **Devices**, and breaches on **Alerts**.
- **The money shot:** cut the Pi's internet (e.g. disable its modem/WiFi) for ~10 s, then
  restore it — the chart **backfills the gap in order**, nothing lost. That's the SDK's whole
  promise, on real hardware, over the real internet.

---

## Alternatives

- **Railway** (<https://railway.app>): New Project → Deploy from GitHub; it uses the
  `Procfile`. Set the same env var.
- **Fly.io**: `fly launch` (needs a `fly.toml`); set env with `fly secrets set TELEMETRY_API_KEY=…`.
- **No-deploy fallback (if the cloud is flaky during recording):** keep the server on your
  laptop and expose it with a tunnel — `ngrok http 8000` — then point the Pi at the ngrok
  URL. Same result, nothing to deploy.
