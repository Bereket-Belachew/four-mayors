// Narrator voice. Primary: OpenAI text-to-speech through the local server (cached as mp3 next to the
// runs, so the demo never waits). Fallback: the browser's own speech synthesis. One switch: window.voiceOn.
(function () {
  const API = "http://localhost:8766";
  const cache = new Map();   // text -> url (or null when the server can't)
  let current = null;        // currently playing Audio
  window.voiceOn = false;

  async function urlFor(text) {
    if (cache.has(text)) return cache.get(text);
    try {
      const r = await fetch(`${API}/tts`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text }) });
      const j = await r.json(); const url = j.url ? `../${j.url}` : null; cache.set(text, url); return url;
    } catch (e) { cache.set(text, null); return null; }
  }
  // warm the cache for a list of lines (fire and forget)
  window.voicePrefetch = lines => { for (const l of lines) if (l) urlFor(String(l).replace(/<[^>]+>/g, "")); };

  function speakBrowser(text) {
    return new Promise(res => {
      if (!("speechSynthesis" in window)) return res();
      const u = new SpeechSynthesisUtterance(text); u.rate = 0.98; u.pitch = 0.95;
      const voices = speechSynthesis.getVoices(); const pick = voices.find(v => /Daniel|Samantha|Google UK English Male|Alex/.test(v.name)); if (pick) u.voice = pick;
      u.onend = () => res(); u.onerror = () => res(); speechSynthesis.speak(u);
      setTimeout(res, Math.min(12000, 400 + text.length * 70)); // never hang the show
    });
  }
  // speak one line; resolves when the audio ends (or immediately when voice is off)
  window.speak = async function (html) {
    const text = String(html).replace(/<[^>]+>/g, "").replace(/\s+/g, " ").trim();
    if (!window.voiceOn || !text) return;
    window.stopSpeaking();
    const url = await urlFor(text);
    if (!url) return speakBrowser(text);
    return new Promise(res => {
      const a = new Audio(url); current = a; a.volume = 0.95;
      a.onended = () => { if (current === a) current = null; res(); };
      a.onerror = () => { current = null; speakBrowser(text).then(res); };
      a.play().catch(() => speakBrowser(text).then(res));
    });
  };
  window.stopSpeaking = function () { if (current) { try { current.pause(); } catch (e) {} current = null; } if ("speechSynthesis" in window) speechSynthesis.cancel(); };
})();
