"""STT Sofya Test"""

import json
import time
import sys
import os
import pandas as pd

import requests
import jiwer as jw
import websocket as ws
import ssl
from utils import load_resource


def get_res(websocket):
    """Tenta ler com timeout"""
    try:
        result = json.loads(websocket.recv())
        print_result(result)
        return result
    except ws.WebSocketTimeoutException:
        return {}


def print_result(result: dict):
    """Imprime o resultado e o tempo de execução"""
    print(result["is_partial"], round(result["time"], 2), result["data"]["text"])


def test_send_chunks(
    host_ws: str, audio_path: str, language: str = "portuguese", chunk_size=4096
):
    """
    Envia os chunks de áudio para o serviço STT e salva a transcrição final em um arquivo de texto.

    :param audio_path: Caminho do arquivo de áudio (obrigatório).
    :param language: Idioma da transcrição (default = "portuguese").
    :param chunk_size: Tamanho do chunk em bytes (default = 4096).
    """

    sslopt_config = {"cert_reqs": ssl.CERT_NONE}

    # Monta a URL com o idioma apropriado
    url = f"{host_ws}?transcription_language={language}"

    # Cria conexão websocket
    websocket = ws.create_connection(url, sslopt=sslopt_config)
    websocket.settimeout(0.1)

    # Carrega o recurso de áudio usando a função utilitária
    resource = load_resource(audio_path)

    # Divide o áudio em chunks
    audio_bytes = resource["audio"]
    chunks = [
        audio_bytes[i : i + chunk_size] for i in range(0, len(audio_bytes), chunk_size)
    ]

    df_result = pd.DataFrame(columns=["is_partial", "latency", "result"])
    for chunk in chunks:
        websocket.send_bytes(chunk)
        res = get_res(websocket)
        if res:
            df_result.loc[len(df_result)] = [
                res["is_partial"],
                round(res["time"], 2),
                res["data"]["text"],
            ]

    # Tenta receber respostas finais por algumas tentativas
    attempts = 0
    while attempts < 3:
        res = get_res(websocket)
        if res:
            attempts = 0
            df_result.loc[len(df_result)] = [
                res["is_partial"],
                round(res["time"], 2),
                res["data"]["text"],
            ]
        else:
            attempts += 1
            time.sleep(1)

    pd.set_option("max_colwidth", 800)
    print("Latency Stats:\n", df_result["latency"].describe())

    # Concatena todas as partes finais (is_partial == False) em ordem.
    # Se não houver respostas finais, utiliza todas as mensagens obtidas.
    non_partial = df_result[df_result["is_partial"] == True]
    if not non_partial.empty:
        final_text = " ".join(non_partial["result"].tolist())
    else:
        final_text = " ".join(df_result["result"].tolist())

    # Define o nome do arquivo de saída com a mesma base do áudio e extensão .txt
    base_name = os.path.splitext(audio_path)[0]
    output_filename = f"{base_name}.txt"

    # Salva o texto final no arquivo de saída
    with open(output_filename, "w", encoding="utf-8") as f:
        f.write(final_text)
    print("Transcrição final salva em:", output_filename)

    # Fecha o websocket
    websocket.close()


if __name__ == "__main__":
    while True:
        # Caso rode diretamente: python stt_test.py <host_ws> <audio_path> [idioma]
        if len(sys.argv) < 3:
            print("Uso: python stt_test.py <host_ws> <audio_path> [idioma]")
            sys.exit(1)

        # Argumento obrigatório: host_ws
        host_ws = sys.argv[1]

        # Argumento obrigatório: caminho do áudio
        audio_path = sys.argv[2]

        # Argumento opcional: idioma (default = portuguese)
        if len(sys.argv) > 3:
            language = sys.argv[3]
        else:
            language = "portuguese"

        print("Starting STT Sofya Test")
        test_send_chunks(
            host_ws=host_ws, audio_path=audio_path, language=language, chunk_size=8192
        )
        print("STT Sofya Test Completed")