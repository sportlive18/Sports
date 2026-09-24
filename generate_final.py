import os
import re          # <-- ADDED
import json
import requests
from concurrent.futures import ThreadPoolExecutor

# ----------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------
JSON_URL = "https://sportlink-jtv.pages.dev/sports.json"
OUTPUT_DIR = "Channel"

# ----------------------------------------------------------------------
# HTML Template (501-style Shaka Player with ClearKey DRM)
# ----------------------------------------------------------------------
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{CHANNEL_NAME}</title>
  <script src="https://pl31358401.profitableratecpmnetwork.com/a3/81/41/a38141b4ff99f6ef8dbf9dc5f76bd86b.js"></script>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/shaka-player/4.7.11/shaka-player.ui.min.js" crossorigin="anonymous"></script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/shaka-player/4.7.11/controls.min.css" crossorigin="anonymous">
  <!-- Google tag (gtag.js) -->
  <script async src="https://www.googletagmanager.com/gtag/js?id=G-FMP9REY96D"></script>
  <script>
    window.dataLayer = window.dataLayer || [];
    function gtag(){dataLayer.push(arguments);}
    gtag('js', new Date());
    gtag('config', 'G-FMP9REY96D');
  </script>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    html, body {
      height: 100vh; width: 100vw;
      background: #000;
      overflow: hidden;
      font-family: system-ui, -apple-system, sans-serif;
    }
    .shaka-video-container {
      position: fixed;
      inset: 0;
      width: 100%;
      height: 100%;
    }
    video {
      width: 100%;
      height: 100%;
      object-fit: contain;
      background: #000;
    }
    .shaka-spinner-container,
    .shaka-spinner,
    .shaka-spinner-svg {
      display: none !important;
      visibility: hidden !important;
      opacity: 0 !important;
    }
  </style>
</head>
<body>

  <div class="shaka-video-container" data-shaka-player>
    <video autoplay playsinline preload="metadata" poster="https://webiptv.updatesbyrahul.site/weiptv.webp"></video>
  </div>

  <script>
    document.addEventListener('DOMContentLoaded', async () => {
      shaka.polyfill.installAll();
      if (!shaka.Player.isBrowserSupported()) {
        console.error('Browser not supported');
        return;
      }

      const video = document.querySelector('video');
      const player = new shaka.Player();
      await player.attach(video);

      const container = document.querySelector('.shaka-video-container');
      const ui = new shaka.ui.Overlay(player, container, video);
      ui.configure({
        controlPanelElements: [
          'play_pause',
          'time_and_duration',
          'mute',
          'volume',
          'spacer',
          'quality',
          'fullscreen'
        ],
        volumeBarColors: {
          base: 'rgba(63,187,1,1)',
          level: 'rgb(255,69,0)'
        },
        seekBarColors: {
          base: 'rgb(41,41,163)',
          buffered: 'rgb(35,99,3)',
          played: 'rgba(63,187,1,1)'
        }
      });

      // === ClearKey DRM (channel keys + 501 defaults merged) ===
      const drmConfig = {
        clearKeys: {
          "dd06ecf8f97a4526ba6a4b55e00f931a": "2b8648806e203a44adc5fb1326770c17",
          "3335649259ea47f7a5053d8bdf57cd34": "597c2f698102cb103cdd56723a4695a2"{EXTRA_KEY}
        }
      };

      // === Per-channel stream URL ===
      const streamUrl = "{STREAM_URL}";

      player.configure({
        drm: drmConfig,
        streaming: {
          lowLatencyMode: true,
          bufferingGoal: 20,
          rebufferingGoal: 5,
          bufferBehind: 25,
          retryParameters: {
            timeout: 8000,
            maxAttempts: 5,
            baseDelay: 300,
            backoffFactor: 1.2
          },
          segmentRequestTimeout: 7000,
          segmentPrefetchLimit: 3,
          useNativeHlsOnSafari: true
        },
        manifest: {
          retryParameters: {
            timeout: 8000,
            maxAttempts: 3
          }
        }
      });

      // === Autoplay handling ===
      const attemptAutoplay = async () => {
        try {
          video.muted = false;
          await video.play();
          console.log("Unmuted autoplay successful");
        } catch (e1) {
          console.warn("Unmuted autoplay failed:", e1.message);
          try {
            video.muted = true;
            await video.play();
            console.log("Muted autoplay successful");
          } catch (e2) {
            console.warn("Muted autoplay failed:", e2.message);
          }
        }
      };

      player.addEventListener('error', (event) => {
        console.error('Shaka Player Error:', event.detail);
      });

      try {
        await player.load(streamUrl);
        console.log("Stream loaded successfully");
        if (video.readyState >= 3) attemptAutoplay();
        else video.addEventListener('canplay', attemptAutoplay, { once: true });
      } catch (err) {
        console.error("Stream load error:", err);
      }

      // Auto fullscreen on mobile
      video.addEventListener(
        "play",
        () => {
          if (window.innerWidth <= 768 && !document.fullscreenElement) {
            container.requestFullscreen().catch(() => {});
          }
        },
        { once: true }
      );

      // Enable sound after interaction
      let interacted = false;
      const enableSound = () => {
        if (!interacted && video.muted) {
          video.muted = false;
          interacted = true;
          console.log("Sound enabled after click");
        }
      };
      ["click", "touchstart", "keydown"].forEach((e) =>
        document.addEventListener(e, enableSound, { once: true })
      );

      document.addEventListener("visibilitychange", () => {
        if (!document.hidden && video.paused) attemptAutoplay();
      });
    });
  </script>

  <!-- Anti-debugging -->
  <script src="https://cdn.jsdelivr.net/npm/disable-devtool@latest"></script>
  <script>
    DisableDevtool({
      disable: true,
      disableMenu: true,
      clearLog: true,
      disableSelect: true,
      disableCopy: true,
      disableCut: true,
      disablePaste: true,
      interval: 10,
      disableMobile: true,
      ondevtoolopen: function () {
        window.location.href = "about:blank";
      },
    });
  </script>
</body>
</html>"""


# ----------------------------------------------------------------------
# Helper
# ----------------------------------------------------------------------
def safe_filename(name: str) -> str:
    """Convert channel name to a safe filename like 'fubo-sports-1.html'."""
    clean = name.lower().strip()
    clean = re.sub(r'[^a-z0-9]+', '-', clean)
    clean = clean.strip('-')
    return clean or "channel"


def build_extra_key(key_id: str, key: str) -> str:
    """Return an extra ClearKey JSON entry, or '' if missing."""
    if key_id and key:
        # Escape quotes just in case
        kid = str(key_id).replace('"', '\\"')
        kv  = str(key).replace('"', '\\"')
        return f',\n          "{kid}": "{kv}"'
    return ""


def generate():
    print(f"Fetching JSON from {JSON_URL}...", flush=True)
    try:
        response = requests.get(JSON_URL, timeout=30)
        response.raise_for_status()
        channels = response.json()
    except Exception as e:
        print(f"Failed to fetch remote JSON: {e}", flush=True)
        return

    print(f"Loaded {len(channels)} channels. Generating HTML files...", flush=True)

    # Create output directory
    if os.path.exists(OUTPUT_DIR):
        for fname in os.listdir(OUTPUT_DIR):
            fpath = os.path.join(OUTPUT_DIR, fname)
            try:
                if os.path.isfile(fpath):
                    os.unlink(fpath)
            except Exception as e:
                print(f"Could not delete {fpath}: {e}", flush=True)
    else:
        os.makedirs(OUTPUT_DIR)

    # Generate one HTML file per channel
    for ch in channels:
        name = ch.get("name", "Unknown")
        key_id = ch.get("keyId", "")
        key = ch.get("key", "")
        stream_url = ch.get("streamUrl", "")

        filename = safe_filename(name) + ".html"
        filepath = os.path.join(OUTPUT_DIR, filename)

        extra_key = build_extra_key(key_id, key)

        content = (HTML_TEMPLATE
                   .replace("{CHANNEL_NAME}", name)
                   .replace("{STREAM_URL}", stream_url)
                   .replace("{EXTRA_KEY}", extra_key))

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        print(f"  ✔ {filename}", flush=True)

    print(f"\nDone! Generated {len(channels)} HTML files in '{OUTPUT_DIR}/'.", flush=True)


if __name__ == "__main__":
    generate()
