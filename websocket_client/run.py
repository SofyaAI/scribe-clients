#!/usr/bin/env python3
"""
STT Sofya WS Test (async, real-time pacing)

Requisitos:
  pip install websockets pandas

Exemplos:
  # 1 usuário
  python stt_ws_test.py \
    --host-ws "ws://168.138.225.41:8000" \
    --audio "./audio1.wav" \
    --language portuguese \
    --chunk-ms 20 \
    --pace 1.0 \
    --silence-after 2.0 \
    --idle-timeout 10

  # carga (10 usuários), reusando lista de arquivos em round-robin
  python stt_ws_test.py \
    --host-ws "ws://168.138.225.41:8000" \
    --audios "./audio1.wav,./audio2.wav,./audio3.wav" \
    --users 10 \
    --idle-timeout 20
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union

import pandas as pd
import websockets


# ---------------------------------------------------------------------
# Config / Models
# ---------------------------------------------------------------------

@dataclass(frozen=True)
class ClientConfig:
    host_ws: str
    language: str = "portuguese"
    chunk_duration_ms: int = 20
    pace_factor: float = 1.0
    silence_after_sec: float = 2.0
    idle_timeout: float = 10.0
    ping_interval: float = 30.0
    ping_timeout: float = 60.0
    close_timeout: float = 5.0
    fallback_bytes_per_sec: int = 32000  # caso não seja WAV PCM conhecido
    concat_finals_only: bool = True      # concatena só finais (is_partial=False)


@dataclass
class SessionResult:
    user_id: str
    avg_model_time_s: float
    session_time_s: float
    output_txt_path: Optional[str]
    rows: int


# ---------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------

def _build_url(host_ws: str, language: str) -> str:
    sep = "&" if "?" in host_ws else "?"
    return f"{host_ws}{sep}transcription_language={language}"


async def _wait_remaining(t0: float, bytes_sent: int, bytes_per_sec: int, pace_factor: float) -> None:
    ideal_delay = (bytes_sent / max(1, bytes_per_sec)) / max(1e-9, pace_factor)
    elapsed = time.perf_counter() - t0
    remaining = ideal_delay - elapsed
    if remaining > 0:
        await asyncio.sleep(remaining)


def _safe_json_loads(raw: Union[str, bytes]) -> Optional[dict]:
    try:
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", errors="replace")
        return json.loads(raw)
    except Exception:
        return None


def _extract_text(msg: dict) -> str:
    # esperado: {"data": {"text": "..."}, ...}
    data = msg.get("data") or {}
    text = data.get("text")
    return text if isinstance(text, str) else ""


def _extract_is_partial(msg: dict) -> Optional[bool]:
    v = msg.get("is_partial")
    return v if isinstance(v, bool) else None


def _extract_model_time(msg: dict) -> Optional[float]:
    v = msg.get("time")
    if isinstance(v, (int, float)):
        return float(v)
    return None


def _output_txt_name(audio_path: Path, user_id: str) -> Path:
    # evita colisões em modo carga
    return audio_path.with_suffix(f".{user_id}.txt")


# ---------------------------------------------------------------------
# Envio "tipo browser" (tempo real)
# ---------------------------------------------------------------------

async def send_chunks_real_time(
    websocket,
    audio_file_path: Union[str, Path],
    *,
    chunk_duration_ms: int,
    pace_factor: float,
    silence_after_sec: float,
    fallback_bytes_per_sec: int,
) -> None:
    """
    Envia áudio simulando microfone:
      - WAV: calcula chunk por frames (sample_rate/channels/sample_width)
      - Não-WAV: lê bytes e usa fallback_bytes_per_sec p/ ritmo
    Ao final, manda silêncio (zeros) por silence_after_sec.
    """
    audio_path = Path(audio_file_path)

    if audio_path.suffix.lower() == ".wav":
        wf = wave.open(str(audio_path), "rb")
        try:
            sample_rate = wf.getframerate()
            channels = wf.getnchannels()
            sample_width = wf.getsampwidth()
            bytes_per_sec = sample_rate * channels * sample_width

            frames_per_chunk = int(sample_rate * chunk_duration_ms / 1000)
            chunk_size = max(1, frames_per_chunk * channels * sample_width)

            def read_method(n: int) -> bytes:
                # wave.readframes recebe "frames", então convertemos
                frames = max(1, n // (channels * sample_width))
                return wf.readframes(frames)

            # 1) Envia áudio real
            while True:
                t0 = time.perf_counter()
                chunk = read_method(chunk_size)
                if not chunk:
                    break
                await websocket.send(chunk)
                await _wait_remaining(t0, len(chunk), bytes_per_sec, pace_factor)

            # 2) Envia silêncio extra
            silence_bytes_total = int(bytes_per_sec * max(0.0, silence_after_sec))
            if silence_bytes_total > 0:
                silence_chunk = b"\x00" * chunk_size
                bytes_sent = 0
                while bytes_sent < silence_bytes_total:
                    t0 = time.perf_counter()
                    send_len = min(chunk_size, silence_bytes_total - bytes_sent)
                    await websocket.send(silence_chunk[:send_len])
                    bytes_sent += send_len
                    await _wait_remaining(t0, send_len, bytes_per_sec, pace_factor)

        finally:
            wf.close()

    else:
        # raw bytes (pcm/etc)
        bytes_per_sec = fallback_bytes_per_sec
        chunk_size = max(1, int(bytes_per_sec * chunk_duration_ms / 1000))

        with open(audio_path, "rb") as f:
            # 1) Envia áudio real
            while True:
                t0 = time.perf_counter()
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                await websocket.send(chunk)
                await _wait_remaining(t0, len(chunk), bytes_per_sec, pace_factor)

            # 2) Silêncio extra
            silence_bytes_total = int(bytes_per_sec * max(0.0, silence_after_sec))
            if silence_bytes_total > 0:
                silence_chunk = b"\x00" * chunk_size
                bytes_sent = 0
                while bytes_sent < silence_bytes_total:
                    t0 = time.perf_counter()
                    send_len = min(chunk_size, silence_bytes_total - bytes_sent)
                    await websocket.send(silence_chunk[:send_len])
                    bytes_sent += send_len
                    await _wait_remaining(t0, send_len, bytes_per_sec, pace_factor)


# ---------------------------------------------------------------------
# Recepção
# ---------------------------------------------------------------------

async def receive_responses(
    websocket,
    *,
    user_id: str,
    idle_timeout: float,
    df: pd.DataFrame,
) -> None:
    """
    Lê mensagens até ficar idle por `idle_timeout`.
    Armazena no dataframe: is_partial, latency(time), text.
    """
    while True:
        try:
            raw_msg = await asyncio.wait_for(websocket.recv(), timeout=idle_timeout)
        except asyncio.TimeoutError:
            print(f"[{user_id}] Idle timeout ({idle_timeout}s); encerrando recepção.")
            break
        except websockets.exceptions.ConnectionClosed:
            print(f"[{user_id}] Servidor fechou a conexão.")
            break

        msg = _safe_json_loads(raw_msg)
        if not isinstance(msg, dict):
            # ignora lixo/bytes não-JSON
            continue

        is_partial = _extract_is_partial(msg)
        model_time = _extract_model_time(msg)
        text = _extract_text(msg)

        # imprime só quando tiver texto
        if text:
            tag = "P" if is_partial else "F"
            print(f"[{user_id}] ({tag}) {text}")

        # salva linha (mesmo sem texto, se quiser medir latência)
        df.loc[len(df)] = [
            is_partial if is_partial is not None else None,
            round(model_time, 4) if model_time is not None else None,
            text,
        ]


# ---------------------------------------------------------------------
# Sessão 1 usuário
# ---------------------------------------------------------------------

async def run_single_session(
    cfg: ClientConfig,
    audio_path: Union[str, Path],
    user_id: str,
) -> SessionResult:
    url = _build_url(cfg.host_ws, cfg.language)
    audio_path = Path(audio_path)

    df = pd.DataFrame(columns=["is_partial", "latency_s", "result"])

    t_session0 = time.perf_counter()
    output_txt: Optional[str] = None

    async with websockets.connect(
        url,
        ping_interval=cfg.ping_interval,
        ping_timeout=cfg.ping_timeout,
        close_timeout=cfg.close_timeout,
        max_size=None,  # evita falhar com mensagens grandes
    ) as websocket:
        sender = asyncio.create_task(
            send_chunks_real_time(
                websocket,
                audio_path,
                chunk_duration_ms=cfg.chunk_duration_ms,
                pace_factor=cfg.pace_factor,
                silence_after_sec=cfg.silence_after_sec,
                fallback_bytes_per_sec=cfg.fallback_bytes_per_sec,
            )
        )
        receiver = asyncio.create_task(
            receive_responses(
                websocket,
                user_id=user_id,
                idle_timeout=cfg.idle_timeout,
                df=df,
            )
        )

        # espera o envio terminar; recepção encerra por timeout
        await sender
        await receiver

    t_session1 = time.perf_counter()
    session_time = t_session1 - t_session0

    # stats latência
    latencies = [x for x in df["latency_s"].tolist() if isinstance(x, (int, float))]
    avg_model_time = float(statistics.mean(latencies)) if latencies else 0.0

    # texto final
    if cfg.concat_finals_only:
        finals = df[df["is_partial"] == False]  # noqa: E712
        chosen = finals if not finals.empty else df
    else:
        chosen = df

    final_text = " ".join([t for t in chosen["result"].tolist() if isinstance(t, str) and t.strip()]).strip()

    # salva .txt
    if final_text:
        out_path = _output_txt_name(audio_path, user_id)
        out_path.write_text(final_text, encoding="utf-8")
        output_txt = str(out_path)
        print(f"[{user_id}] Transcrição salva em: {output_txt}")
    else:
        print(f"[{user_id}] Nenhum texto final para salvar.")

    # imprime describe
    if latencies:
        pd.set_option("max_colwidth", 800)
        print(f"[{user_id}] Latency Stats:\n{pd.Series(latencies).describe()}")

    return SessionResult(
        user_id=user_id,
        avg_model_time_s=avg_model_time,
        session_time_s=session_time,
        output_txt_path=output_txt,
        rows=len(df),
    )


# ---------------------------------------------------------------------
# Carga (N usuários)
# ---------------------------------------------------------------------

def _print_stats(label: str, values: list[float]) -> None:
    if not values:
        print(f"{label:<18}: sem valores")
        return
    # p95
    if len(values) >= 2:
        p95 = statistics.quantiles(values, n=100)[94]
    else:
        p95 = values[0]
    print(
        f"{label:<18}: "
        f"média={statistics.mean(values):6.3f}s  "
        f"mediana={statistics.median(values):6.3f}s  "
        f"mín={min(values):6.3f}s  "
        f"máx={max(values):6.3f}s  "
        f"P95={p95:6.3f}s"
    )


async def run_load(cfg: ClientConfig, audio_paths: list[Path], users: int) -> None:
    if not audio_paths:
        raise ValueError("Lista de áudios vazia.")

    tasks = []
    for i in range(users):
        audio_path = audio_paths[i % len(audio_paths)]
        user_id = f"user_{i+1}"
        tasks.append(run_single_session(cfg, audio_path, user_id))

    results = await asyncio.gather(*tasks, return_exceptions=False)

    print("\n--- Resultados por usuário ---")
    for r in results:
        print(
            f"{r.user_id:<8}: modelo={r.avg_model_time_s:6.3f}s | sessão={r.session_time_s:6.3f}s | rows={r.rows}"
        )

    model_times = [r.avg_model_time_s for r in results if r.avg_model_time_s > 0]
    session_times = [r.session_time_s for r in results]

    print("\n--- Estatísticas agregadas ---")
    _print_stats("avg_model_time", model_times)
    _print_stats("session_time", session_times)


# ---------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="STT Sofya WS Test (async real-time)")
    p.add_argument("--host-ws", required=True, help="Ex: ws://ip:8000/ws ou ws://ip:8000")
    p.add_argument("--language", default="portuguese", help="Ex: portuguese")
    p.add_argument("--audio", default=None, help="Caminho de 1 áudio (modo single)")
    p.add_argument("--audios", default=None, help="Lista separada por vírgula (modo carga)")
    p.add_argument("--users", type=int, default=1, help="Número de usuários simultâneos (modo carga)")
    p.add_argument("--chunk-ms", type=int, default=20, help="Duração do chunk em ms (ex: 20)")
    p.add_argument("--pace", type=float, default=1.0, help="1.0 = tempo real; 2.0 = 2x mais rápido")
    p.add_argument("--silence-after", type=float, default=2.0, help="Segundos de silêncio após fim do áudio")
    p.add_argument("--idle-timeout", type=float, default=10.0, help="Timeout sem mensagens para encerrar recepção")
    p.add_argument("--fallback-bps", type=int, default=32000, help="Bytes/s para não-wav (fallback)")
    p.add_argument("--concat-finais-only", action="store_true", help="Concatena só mensagens finais (default recomendado)")
    p.add_argument("--concat-tudo", action="store_true", help="Concatena tudo (parciais+finais)")
    return p.parse_args()


async def main() -> None:
    args = _parse_args()

    concat_finals_only = True
    if args.concat_tudo:
        concat_finals_only = False
    if args.concat_finais_only:
        concat_finals_only = True

    cfg = ClientConfig(
        host_ws=args.host_ws,
        language=args.language,
        chunk_duration_ms=args.chunk_ms,
        pace_factor=args.pace,
        silence_after_sec=args.silence_after,
        idle_timeout=args.idle_timeout,
        fallback_bytes_per_sec=args.fallback_bps,
        concat_finals_only=concat_finals_only,
    )

    # modo single se --audio
    if args.audio:
        r = await run_single_session(cfg, Path(args.audio), user_id="user_1")
        print(
            f"\nuser_1: modelo={r.avg_model_time_s:6.3f}s | sessão={r.session_time_s:6.3f}s | rows={r.rows}"
        )
        return

    # modo carga se --audios + users>1 (ou até 1, mas lista)
    if args.audios:
        audio_paths = [Path(x.strip()) for x in args.audios.split(",") if x.strip()]
        await run_load(cfg, audio_paths, users=max(1, args.users))
        return

    raise SystemExit("Você precisa informar --audio (single) ou --audios (carga).")


if __name__ == "__main__":
    asyncio.run(main())