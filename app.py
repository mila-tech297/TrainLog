"""TrainLog: start met python app.py. Gebruikt alleen de standaardbibliotheek."""
import argparse
from contextlib import contextmanager
import datetime as dt
import json
import math
import os
from pathlib import Path
import secrets
import sqlite3
import threading
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
DATABASE = ROOT / "data" / "trainlog.sqlite3"
TOKEN = secrets.token_urlsafe(32)


@contextmanager
def connect():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def initialize():
    DATABASE.parent.mkdir(exist_ok=True)
    with connect() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS workouts (
                id INTEGER PRIMARY KEY, date TEXT NOT NULL,
                distance REAL NOT NULL, duration REAL NOT NULL, note TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS goal (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                distance REAL NOT NULL, deadline TEXT NOT NULL
            );
        """)


def number(value, maximum):
    if isinstance(value, bool):
        raise ValueError("Vul een geldig positief getal in.")
    try:
        result = float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        raise ValueError("Vul een geldig positief getal in.")
    if not math.isfinite(result) or not 0 < result <= maximum:
        raise ValueError(f"Vul een getal groter dan 0 en maximaal {maximum} in.")
    return result


def date_value(value):
    try:
        return dt.date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValueError("Vul een geldige datum in.")


def state():
    with connect() as db:
        workouts = [dict(row) for row in db.execute("SELECT * FROM workouts ORDER BY date DESC, id DESC")]
        goal = db.execute("SELECT * FROM goal WHERE id = 1").fetchone()
    return {"workouts": workouts, "goal": dict(goal) if goal else None,
            "ai_available": bool(os.getenv("OPENAI_API_KEY")), "token": TOKEN,
            "today": dt.date.today().isoformat()}


def weekly_summary(use_ai):
    today = dt.date.today()
    start = today - dt.timedelta(days=6)
    previous = start - dt.timedelta(days=7)
    workouts = state()["workouts"]
    current = [w for w in workouts if start.isoformat() <= w["date"] <= today.isoformat()]
    earlier = [w for w in workouts if previous.isoformat() <= w["date"] < start.isoformat()]
    if not current:
        raise ValueError("Je hebt de afgelopen zeven dagen nog geen trainingen opgeslagen.")
    distance = round(sum(w["distance"] for w in current), 2)
    duration = round(sum(w["duration"] for w in current), 1)
    old_distance = round(sum(w["distance"] for w in earlier), 2)
    text = (f"De afgelopen zeven dagen heb je {len(current)} keer hardgelopen: "
            f"{distance:g} km in {duration:g} minuten. ")
    if earlier:
        difference = round(distance - old_distance, 2)
        text += f"Dat is {abs(difference):g} km {'meer' if difference >= 0 else 'minder'} dan in de zeven dagen daarvoor ({old_distance:g} km)."
    else:
        text += "Er zijn geen trainingen uit de zeven dagen daarvoor om mee te vergelijken."
    if not use_ai:
        return {"text": text, "source": "Berekend weekoverzicht · geen AI"}
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise ValueError("AI is nog niet ingesteld. Stel OPENAI_API_KEY in op de Python-server; zie README.md.")
    payload = {
        "model": os.getenv("OPENAI_MODEL", "gpt-4.1-mini"), "store": False,
        "instructions": "Schrijf in het Nederlands een korte, vriendelijke samenvatting van maximaal 120 woorden van de hardloopgegevens. Gebruik uitsluitend de opgegeven feiten. Verzin geen resultaten, oorzaken, gezondheidseffecten of trainingsadvies. Vermeld dat ontbrekende registraties geen bewijs zijn dat iemand niet heeft gesport.",
        "input": json.dumps({"berekend_overzicht": text, "doel": state()["goal"]}, ensure_ascii=False),
        "max_output_tokens": 350,
    }
    request = Request("https://api.openai.com/v1/responses", data=json.dumps(payload).encode(),
                      headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    try:
        with urlopen(request, timeout=45) as response:
            result = json.load(response)
    except HTTPError as error:
        raise ValueError(f"De AI-aanvraag is mislukt (HTTP {error.code}). Controleer je API-sleutel, tegoed en modelinstelling.")
    except (URLError, TimeoutError):
        raise ValueError("De AI-dienst is niet bereikbaar. Probeer later opnieuw.")
    parts = [part["text"] for item in result.get("output", [])
             for part in item.get("content", []) if part.get("type") == "output_text"]
    if not parts:
        raise ValueError("De AI heeft geen samenvatting teruggestuurd. Probeer opnieuw.")
    return {"text": "\n".join(parts), "source": "AI-samenvatting · OpenAI"}


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT / "static"), **kwargs)

    def json_response(self, value, status=200):
        data = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/api/state":
            return self.json_response(state())
        if self.path.startswith("/api/"):
            return self.json_response({"error": "Niet gevonden."}, 404)
        return super().do_GET()

    def do_POST(self):
        if self.headers.get("X-Trainlog-Token") != TOKEN:
            return self.json_response({"error": "Ververs de pagina en probeer opnieuw."}, 403)
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 10000:
                raise ValueError("Het verzoek is te groot of leeg.")
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict):
                raise ValueError("Ongeldig verzoek.")
            if self.path == "/api/workouts":
                date = date_value(body.get("date"))
                if date > dt.date.today():
                    raise ValueError("Een training mag niet in de toekomst liggen.")
                distance = number(body.get("distance"), 1000)
                duration = number(body.get("duration"), 10080)
                note = body.get("note", "")
                if not isinstance(note, str) or len(note) > 500:
                    raise ValueError("Gebruik maximaal 500 tekens voor je notitie.")
                with connect() as db:
                    db.execute("INSERT INTO workouts(date, distance, duration, note) VALUES (?, ?, ?, ?)",
                               (date.isoformat(), distance, duration, note.strip()))
            elif self.path == "/api/workouts/delete":
                workout_id = body.get("id")
                if type(workout_id) is not int:
                    raise ValueError("Ongeldige training.")
                with connect() as db:
                    db.execute("DELETE FROM workouts WHERE id = ?", (workout_id,))
            elif self.path == "/api/goal":
                distance = number(body.get("distance"), 1000)
                deadline = date_value(body.get("deadline"))
                if deadline < dt.date.today():
                    raise ValueError("Kies een doeldatum vanaf vandaag.")
                with connect() as db:
                    db.execute("INSERT INTO goal VALUES (1, ?, ?) ON CONFLICT(id) DO UPDATE SET distance=excluded.distance, deadline=excluded.deadline",
                               (distance, deadline.isoformat()))
            elif self.path == "/api/summary":
                return self.json_response(weekly_summary(body.get("ai") is True))
            else:
                return self.json_response({"error": "Niet gevonden."}, 404)
            self.json_response(state())
        except (ValueError, TypeError) as error:
            self.json_response({"error": str(error)}, 400)
        except Exception:
            self.json_response({"error": "Er ging iets mis op de server. Probeer opnieuw."}, 500)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TrainLog + DoelTracker")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--open", action="store_true", help="Open de app automatisch in je browser")
    args = parser.parse_args()
    initialize()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    if args.open:
        threading.Timer(0.5, webbrowser.open, args=(f"http://localhost:{args.port}",)).start()
    print(f"TrainLog draait op http://{args.host}:{args.port} · stoppen met Ctrl+C", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()
