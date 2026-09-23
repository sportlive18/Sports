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
# HTML Template (single-file Shaka Player with ClearKey DRM)
# ----------------------------------------------------------------------
HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
 <script src="https://pl31358401.profitableratecpmnetwork.com/a3/81/41/a38141b4ff99f6ef8dbf9dc5f76bd86b.js"></script>
  <title>{CHANNEL_NAME}</title>
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
      background: #000;
      height: 100vh;
      width: 100vw;
      overflow: hidden;
      font-family: system-ui, -apple-system, sans-serif;
    }
    .shaka-video-container {
      position: absolute;
      inset: 0;
      width: 100%;
      height: 100%;
    }
    video {
      width: 100%;
      height: 100%;
      background: #000;
      object-fit: contain;
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
    <video autoplay playsinline preload="metadata" poster=""></video>
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
          'play_pause', 'time_and_duration', 'mute', 'volume',
          'spacer', 'language', 'captions', 'picture_in_picture',
          'quality', 'fullscreen'
        ],
        volumeBarColors: {
          base: 'rgba(0, 136, 255, 0.3)',
          level: 'rgb(0, 136, 255)'
        },
        seekBarColors: {
          base: 'rgba(0, 136, 255, 0.3)',
          buffered: 'rgba(0, 136, 255, 0.6)',
          played: 'rgb(0, 136, 255)'
        }
      });

      // ClearKey DRM
      let drmConfig = {
        clearKeys: {
          "{KEY_ID}": "{KEY}"
        }
      };

      let streamUrl = "{STREAM_URL}";

      player.configure({
        drm: drmConfig,
        streaming: {
          lowLatencyMode: true,
          bufferingGoal: 15,
          rebufferingGoal: 2,
          bufferBehind: 15,
          retryParameters: {
            timeout: 10000,
            maxAttempts: 5,
            baseDelay: 300,
            backoffFactor: 1.2
          },
          segmentRequestTimeout: 8000,
          segmentPrefetchLimit: 2,
          useNativeHlsOnSafari: true
        },
        manifest: {
          retryParameters: {
            timeout: 8000,
            maxAttempts: 3
          }
        }
      });

      player.addEventListener('error', (event) => {
        console.error('Shaka Player Error:', event.detail);
      });

      try {
        await player.load(streamUrl);
        console.log("Stream loaded successfully");
      } catch (error) {
        console.error('Load error:', error);
      }
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

        content = (HTML_TEMPLATE
                   .replace("{CHANNEL_NAME}", name)
                   .replace("{KEY_ID}", key_id)
                   .replace("{KEY}", key)
                   .replace("{STREAM_URL}", stream_url))

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        print(f"  ✔ {filename}", flush=True)

    print(f"\nDone! Generated {len(channels)} HTML files in '{OUTPUT_DIR}/'.", flush=True)


if __name__ == "__main__":
    generate()
