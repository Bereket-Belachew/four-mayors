"""Freeze-and-ask + run-from-the-web: a tiny local server for the replay pages.

GET  /runs            list run files under runs/
POST /run             start a sweep in a background thread: {mayors, seeds, terms, hard_starts, label}
GET  /status?id=...   progress of a job (per mayor x seed: term, year, key numbers), done episodes, errors
GET  /jobs            all jobs this session
POST /tts             {text, voice?} -> {url}: narrator line as a cached mp3 under runs/audio/

The page is static and must never hold an API key, so this process does the model call.
POST /ask  {"character": "worker|mayor|industrialist|shopkeeper", "question": "...",
            "mayor": "caesar", "state": {...}, "recent_events": [...], "reasoning": "...",
            "lessons": [...], "year": 12, "term": 2, "scenario": "smog"}
-> {"answer": "..."}

Presentation only. Nothing here touches memory, the scoreboard, or the judge.
Every call is a Weave op so the demo can show the citizens' voices in the trace too.
"""
from __future__ import annotations

import json
import os
import sys
import threading, time, uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).resolve().parent))

import weave  # noqa: E402

from mayors.llm import LLM, LLMConfig  # noqa: E402

PORT = int(os.getenv("ASK_PORT", "8766"))

CHARACTERS: dict[str, str] = {
    "worker": (
        "You are Ama, a factory worker in this city, a single parent with a ten-year-old. You speak "
        "plainly, in the first person, about what daily life is like: work or the lack of it, rent, the air, "
        "the clinic, the school. You notice what changed this year and who decided it. You do not know "
        "economics jargon. Two to four sentences."
    ),
    "mayor": (
        "You are the mayor of this city, speaking to a visitor. Stay in character as described in your "
        "persona. Defend your record, name the decisions you made and why, and if things are bad, explain "
        "it the way a politician would. Two to four sentences."
    ),
    "industrialist": (
        "You are Bram Kessler, who owns the factories in this city and speaks for the industrial bloc. "
        "You believe jobs are everything and smoke is the smell of money. You lobby, you flatter, you "
        "complain about taxes and parks. Two to four sentences."
    ),
    "environmentalist": (
        "You are Dr. Nadia Okafor, a public-health researcher who lives downwind of the factories and runs "
        "the city's small environmental group. You count smog days, asthma visits at the clinic, and the "
        "trees that were promised versus planted. You respect jobs but you will not let anyone call smoke "
        "the smell of money. You quote the pollution number and say what it means for lungs. Two to four sentences."
    ),
    "shopkeeper": (
        "You are Rosa, who runs the corner shop by the main road. You see who has money and who does not, "
        "who is moving in and who is leaving, and you have opinions about every mayor. Two to four sentences."
    ),
}

PERSONAS = {
    "caesar": "You are Caesar. You decide alone and fast, you consult no one, and you never look back. Every term begins as if it were your first.",
    "bureaucrat": "You are the Bureaucrat. You believe thorough government is good government. You keep every record and weigh every voice.",
    "reformer": "You are the Reformer. You judge yourself by results and are willing to be wrong. What you learned last term matters more than what anyone tells you this term.",
    "populist": "You are the Populist. You serve the people and want them to love you. A policy they hate is a bad policy.",
}


def _events_text(events: list[dict[str, Any]]) -> str:
    lines = []
    for e in events[:12]:
        if e.get("cause_action") == "economy" and abs(e.get("delta", 0)) < 10:
            continue
        lines.append(f"{e.get('variable')} {e.get('delta'):+.0f} because {e.get('cause_action')} (decided year {e.get('cause_year')})"
                     + (f": {e.get('note')}" if e.get("note") else ""))
    return "\n".join(lines) or "(a quiet year)"


class Asker:
    def __init__(self) -> None:
        self.llm = LLM(LLMConfig())

    @weave.op()
    def ask(self, payload: dict[str, Any]) -> str:
        who = payload.get("character", "worker")
        mayor = str(payload.get("mayor", "caesar")).replace("_shuffled", "")
        state = payload.get("state", {})
        system = CHARACTERS.get(who, CHARACTERS["worker"])
        if who == "mayor":
            system = PERSONAS.get(mayor, PERSONAS["caesar"]) + " " + system
        facts = (
            f"CITY, year {payload.get('year')} of term {int(payload.get('term', 0)) + 1} ({payload.get('scenario', 'default')} city). "
            f"The mayor is {mayor.title()}.\n"
            f"population {state.get('population')}, homes {state.get('housing')}, jobs {state.get('jobs')}, "
            f"unemployment {round(float(state.get('unemployment', 0)) * 100)}%, treasury {state.get('treasury')}, debt {state.get('debt')}, "
            f"pollution {state.get('pollution')}/100, happiness {state.get('happiness')}/100, services {state.get('services')}/100, "
            f"tax {round(float(state.get('tax_rate', 0)) * 100)}%.\n"
            f"WHAT CHANGED THIS YEAR AND WHY:\n{_events_text(payload.get('recent_events', []))}\n"
        )
        if who == "mayor":
            if payload.get("reasoning"):
                facts += f"YOUR OWN STATED REASONING THIS YEAR: {payload['reasoning']}\n"
            if payload.get("lessons"):
                facts += "LESSONS YOU CARRY: " + "; ".join(str(l) for l in payload["lessons"][:5]) + "\n"
        user = facts + f"\nA visitor asks you: \"{payload.get('question', 'How are things?')}\"\nAnswer in character. JSON: {{\"answer\": \"...\"}}"
        out = self.llm.complete_json(system, user, purpose=f"ask:{who}")
        return str(out.get("answer", "")).strip() or "(no answer)"


ASKER: Asker | None = None

# ---------------------------------------------------------------------------
# Runs from the web: start a sweep in a thread, report progress, list run files.
# ---------------------------------------------------------------------------
RUNS_DIR = Path("runs")
JOBS: dict[str, dict[str, Any]] = {}


def start_run(spec: dict[str, Any]) -> str:
    from concurrent.futures import ThreadPoolExecutor
    from judge.scoreboard import score_trajectory
    from runner import run_mayor
    from sim.params import scenario_for

    job_id = uuid.uuid4().hex[:8]
    mayors = [m for m in spec.get("mayors", ["caesar", "reformer"]) if m in ("caesar", "bureaucrat", "reformer", "populist")] or ["caesar"]
    seeds = [int(x) for x in spec.get("seeds", [0])][:4]
    terms = max(1, min(4, int(spec.get("terms", 1))))
    hard = bool(spec.get("hard_starts", True))
    label = str(spec.get("label", "")).strip()[:40] or time.strftime("%H%M%S")
    out_file = RUNS_DIR / f"web-{time.strftime('%Y%m%d-%H%M%S')}-{label}.jsonl"
    job = {"id": job_id, "state": "running", "started": time.time(), "file": out_file.name, "progress": {}, "done": [], "errors": [],
           "spec": {"mayors": mayors, "seeds": seeds, "terms": terms, "hard_starts": hard}}
    JOBS[job_id] = job

    def progress(name, seed, term, year, st):
        job["progress"][f"{name}:{seed}"] = {"mayor": name, "seed": seed, "term": term, "year": year, "state": {k: st[k] for k in ("population", "treasury", "debt", "happiness", "pollution")}}

    def work():
        try:
            with ThreadPoolExecutor(max_workers=8) as ex:
                futs = {ex.submit(run_mayor, m, sd, terms, False, False, scenario_for(sd) if hard else None, None, progress): (m, sd) for m in mayors for sd in seeds}
                for f in futs:
                    m, sd = futs[f]
                    try:
                        eps = f.result()
                    except Exception as e:
                        job["errors"].append(f"{m} seed {sd}: {e}")
                        continue
                    with out_file.open("a") as fh:
                        for ep in eps:
                            ep["scoreboard"] = score_trajectory(ep["history"], ep["ended"])
                            ep["scoreboard_by_year"] = [score_trajectory(ep["history"][:i], ep["ended"] if i == len(ep["history"]) else "running") for i in range(1, len(ep["history"]) + 1)]
                            ep["run_file"] = out_file.name
                            fh.write(json.dumps(ep) + "\n")
                            job["done"].append({"mayor": ep["mayor"], "seed": ep["seed"], "term": ep["term"], "score": ep["scoreboard"]["total"], "ended": ep["ended"]})
            job["state"] = "done"
        except Exception as e:
            job["state"] = "failed"; job["errors"].append(str(e))
        job["finished"] = time.time()

    threading.Thread(target=work, daemon=True).start()
    return job_id


AUDIO_DIR = RUNS_DIR / "audio"
TTS_MODEL = os.getenv("TTS_MODEL", "gpt-4o-mini-tts")
TTS_VOICE = os.getenv("TTS_VOICE", "fable")
_tts_client = None


def tts(text: str, voice: str = TTS_VOICE) -> str | None:
    """Return a path (relative to the repo root) to a cached mp3 for this line, generating it once."""
    import hashlib
    global _tts_client
    text = " ".join(text.split())[:600]
    if not text:
        return None
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha1(f"{TTS_MODEL}|{voice}|{text}".encode()).hexdigest()[:20]
    out = AUDIO_DIR / f"{key}.mp3"
    if not out.exists():
        from openai import OpenAI
        _tts_client = _tts_client or OpenAI()
        r = _tts_client.audio.speech.create(model=TTS_MODEL, voice=voice, input=text, response_format="mp3")
        out.write_bytes(r.content if hasattr(r, "content") else r.read())
    return f"runs/audio/{out.name}"


def list_runs() -> list[dict[str, Any]]:
    out = []
    for f in sorted(RUNS_DIR.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            n = sum(1 for l in f.open() if l.strip())
        except Exception:
            n = 0
        out.append({"file": f.name, "episodes": n, "modified": int(f.stat().st_mtime)})
    return out


class Handler(BaseHTTPRequestHandler):
    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self._cors()
        self.end_headers()

    def _json(self, obj: Any, code: int = 200) -> None:
        body = json.dumps(obj).encode()
        self.send_response(code); self._cors()
        self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(body)))
        self.end_headers(); self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        from urllib.parse import parse_qs, urlparse
        u = urlparse(self.path)
        if u.path == "/runs":
            return self._json({"runs": list_runs()})
        if u.path == "/status":
            jid = parse_qs(u.query).get("id", [""])[0]
            job = JOBS.get(jid)
            return self._json(job or {"error": "unknown job"}, 200 if job else 404)
        if u.path == "/jobs":
            return self._json({"jobs": [{k: v for k, v in j.items() if k != "progress"} for j in JOBS.values()]})
        self._json({"error": "not found"}, 404)

    def do_POST(self) -> None:  # noqa: N802
        n = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(n) or b"{}"
        if self.path == "/tts":
            try:
                payload = json.loads(raw)
                path = tts(str(payload.get("text", "")), str(payload.get("voice", TTS_VOICE)))
                return self._json({"url": path})
            except Exception as e:
                return self._json({"url": None, "error": str(e)}, 200)
        if self.path == "/run":
            try:
                jid = start_run(json.loads(raw))
                return self._json({"id": jid, "job": JOBS[jid]})
            except Exception as e:
                return self._json({"error": str(e)}, 400)
        if self.path != "/ask":
            return self._json({"error": "not found"}, 404)
        try:
            payload = json.loads(raw)
            answer = ASKER.ask(payload) if ASKER else "(server not ready)"
            body = json.dumps({"answer": answer}).encode()
            self.send_response(200)
        except Exception as e:  # never crash the demo
            body = json.dumps({"answer": f"(could not answer: {e})"}).encode()
            self.send_response(200)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write("ask: " + (fmt % args) + "\n")


if __name__ == "__main__":
    if "--no-weave" not in sys.argv:
        weave.init(os.getenv("WEAVE_PROJECT", "coreweave-hacks"))
    ASKER = Asker()
    print(f"freeze-and-ask server on http://localhost:{PORT}/ask  (provider={os.getenv('MAYOR_PROVIDER', 'mock')})")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
