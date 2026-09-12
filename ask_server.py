"""Freeze-and-ask: a tiny local server so the replay page can put a question to someone in the city.

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
from http.server import BaseHTTPRequestHandler, HTTPServer
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


class Handler(BaseHTTPRequestHandler):
    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/ask":
            self.send_response(404)
            self._cors()
            self.end_headers()
            return
        n = int(self.headers.get("Content-Length", "0"))
        try:
            payload = json.loads(self.rfile.read(n) or b"{}")
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
    HTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
