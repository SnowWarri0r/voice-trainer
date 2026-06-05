# Voice Trainer

Real-time visual feedback for **pitch (F0)** and **vocal resonance** — see whether your voice sits inside a chosen target range as you speak.

## Local development (one command)

    make install   # first run: create backend venv + install deps
    make dev       # backend (:8000) + frontend dev server (:5173)

Open http://localhost:5173 , click **Start**, and allow microphone access.

## Tests

    make test      # backend pytest

## Deploy (one command)

    docker compose up --build -d

Open http://localhost:8000 (frontend and backend share a single port).

## Architecture

- **Frontend** (Vite/TS): WebAudio captures the mic → Int16 PCM chunks → WebSocket.
- **Backend** (FastAPI): a rolling buffer feeds parselmouth to estimate F0, formants, and a vowel-normalized resonance value, pushed back per frame; it also serves the built frontend.
- **Analysis engine** (`backend/voicetrainer/analysis/`): pure functions shared by the live path and (later) offline review, so both stay consistent.

## Status & scope

- MVP: a two-track live view (pitch + resonance) checked against a configurable target band.
- Resonance uses a built-in generic vowel model; personal calibration, a single-vowel locator view, and recorded-session review are later stages.
- Only the measurable layer (pitch / formants / resonance) is scored — no subjective judgments about tone.
