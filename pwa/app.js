(() => {
  "use strict";

  const MONTHS_RO = [
    "ianuarie", "februarie", "martie", "aprilie", "mai", "iunie",
    "iulie", "august", "septembrie", "octombrie", "noiembrie", "decembrie",
  ];

  const audio = document.getElementById("audio");
  const playBtn = document.getElementById("play-btn");
  const playIcon = document.getElementById("play-btn-icon");
  const dateEl = document.getElementById("bulletin-date");
  const progressBar = document.getElementById("progress-bar");
  const timeCurrent = document.getElementById("time-current");
  const timeTotal = document.getElementById("time-total");
  const seekBack = document.getElementById("seek-back");
  const seekFwd = document.getElementById("seek-fwd");
  const statusEl = document.getElementById("status");

  let wakeLock = null;

  function formatDateRo(isoDate) {
    const [y, m, d] = isoDate.split("-").map(Number);
    return `${d} ${MONTHS_RO[m - 1]}`;
  }

  function formatTime(seconds) {
    if (!Number.isFinite(seconds) || seconds < 0) seconds = 0;
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${s.toString().padStart(2, "0")}`;
  }

  function setPlayIcon(isPlaying) {
    playIcon.textContent = isPlaying ? "⏸" : "▶";
    playBtn.setAttribute("aria-label", isPlaying ? "Pauză" : "Redare");
  }

  async function acquireWakeLock() {
    if (!("wakeLock" in navigator)) return;
    try {
      wakeLock = await navigator.wakeLock.request("screen");
    } catch (_) { /* ignore */ }
  }

  function releaseWakeLock() {
    if (wakeLock) {
      wakeLock.release().catch(() => {});
      wakeLock = null;
    }
  }

  function setupMediaSession(title, date) {
    if (!("mediaSession" in navigator)) return;
    navigator.mediaSession.metadata = new MediaMetadata({
      title: "Știri Tată",
      artist: `Buletin din ${formatDateRo(date)}`,
      album: "Știri Tată",
      artwork: [
        { src: "icons/icon-192.png", sizes: "192x192", type: "image/png" },
        { src: "icons/icon-512.png", sizes: "512x512", type: "image/png" },
      ],
    });
    navigator.mediaSession.setActionHandler("play", () => audio.play());
    navigator.mediaSession.setActionHandler("pause", () => audio.pause());
    navigator.mediaSession.setActionHandler("seekbackward", (d) => seek(-(d.seekOffset || 30)));
    navigator.mediaSession.setActionHandler("seekforward", (d) => seek(d.seekOffset || 30));
  }

  function seek(delta) {
    const target = Math.max(0, Math.min(audio.duration || 0, audio.currentTime + delta));
    audio.currentTime = target;
  }

  async function loadManifestAndAudio() {
    statusEl.textContent = "";
    try {
      // Cache-bust manifest so we always see the latest even when the SW is cached.
      const resp = await fetch(`latest.json?t=${Date.now()}`, { cache: "no-cache" });
      if (!resp.ok) throw new Error(`manifest http ${resp.status}`);
      const manifest = await resp.json();

      dateEl.textContent = `Buletin din ${formatDateRo(manifest.date)}`;
      audio.src = `latest.mp3?v=${encodeURIComponent(manifest.date)}`;
      setupMediaSession("Știri Tată", manifest.date);

      if (Number.isFinite(manifest.duration_seconds)) {
        timeTotal.textContent = formatTime(manifest.duration_seconds);
      }
    } catch (err) {
      // Offline / server down: fall back to whatever the SW has cached.
      statusEl.textContent = "Folosim buletinul salvat local.";
      audio.src = "latest.mp3";
      dateEl.textContent = "Buletin din cache";
    }
  }

  // --- event wiring ---

  playBtn.addEventListener("click", async () => {
    if (audio.paused) {
      try {
        await audio.play();
        await acquireWakeLock();
      } catch (err) {
        statusEl.textContent = "Nu pot reda audio. Verifică conexiunea.";
      }
    } else {
      audio.pause();
    }
  });

  seekBack.addEventListener("click", () => seek(-30));
  seekFwd.addEventListener("click", () => seek(30));

  audio.addEventListener("play", () => setPlayIcon(true));
  audio.addEventListener("pause", () => { setPlayIcon(false); releaseWakeLock(); });
  audio.addEventListener("ended", () => { setPlayIcon(false); releaseWakeLock(); });

  audio.addEventListener("loadedmetadata", () => {
    if (Number.isFinite(audio.duration)) {
      timeTotal.textContent = formatTime(audio.duration);
    }
  });

  audio.addEventListener("timeupdate", () => {
    const cur = audio.currentTime || 0;
    const dur = audio.duration || 0;
    timeCurrent.textContent = formatTime(cur);
    if (dur > 0) {
      progressBar.style.width = `${(cur / dur) * 100}%`;
    }
  });

  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible" && wakeLock === null && !audio.paused) {
      acquireWakeLock();
    }
  });

  // Register service worker
  if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => {
      navigator.serviceWorker.register("sw.js").catch(() => {});
    });
  }

  loadManifestAndAudio();
})();
