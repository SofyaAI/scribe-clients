import argparse
import json
from pathlib import Path
from typing import Any, Dict, Optional

import requests


def call_transcriber_api(
    audio_file_path: str,
    url: str,
    override_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Faz uma chamada HTTP POST ao endpoint /api/transcriber, enviando:
    1) Arquivo de áudio (multipart).
    2) override_config (JSON, como string no form field), se fornecido.

    :param audio_file_path: caminho local para o arquivo WAV ou outro formato suportado.
    :param url: endpoint completo, ex: http://localhost:8000/api/transcriber
    :param override_config: dicionário com a configuração de override. Se None,
                            NENHUM campo override_config será enviado.
    :return: dicionário com a resposta JSON do servidor ({"transcription": "...", "metadata": {...}})
    """

    # Monta o multipart/form-data
    with open(audio_file_path, "rb") as audio_file:
        files = {
            "file": ("audio.wav", audio_file, "audio/wav"),
        }

        # Só envia override_config se ele foi explicitamente informado
        data: Dict[str, str] = {}
        if override_config is not None:
            data["override_config"] = json.dumps(override_config)

        response = requests.post(url, data=data, files=files)

    if response.status_code != 200:
        raise RuntimeError(
            f"Request falhou [{response.status_code}] => {response.text}"
        )

    return response.json()


def load_override_config(config_arg: Optional[str]) -> Optional[Dict[str, Any]]:
    """
    Carrega o override_config a partir de:
    - Caminho para arquivo JSON, ou
    - String JSON passada diretamente na linha de comando.

    :param config_arg: valor recebido da flag --config
    :return: dicionário com a configuração ou None se não informado
    """
    if not config_arg:
        return None

    # 1) Se for um caminho de arquivo existente, tenta carregar como JSON
    path = Path(config_arg)
    if path.exists() and path.is_file():
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)

    # 2) Senão, tenta interpretar o valor como JSON inline
    try:
        return json.loads(config_arg)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Não foi possível interpretar --config nem como arquivo nem como JSON válido: {e}"
        ) from e


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Cliente simples para o endpoint /api/transcriber."
    )
    parser.add_argument(
        "audio_path",
        help="Caminho para o arquivo de áudio (ex: meu_audio.wav).",
    )
    parser.add_argument(
        "--endpoint-url",
        "-u",
        required=True,
        help="URL completa do endpoint de transcrição (ex: https://<host>/api/transcriber).",
    )
    parser.add_argument(
        "--config",
        "-c",
        help=(
            "Override de configuração em JSON. "
            "Pode ser (a) caminho para um arquivo .json OU (b) uma string JSON inline. "
            "Se não for informado, nenhum override_config será enviado."
        ),
    )

    args = parser.parse_args()

    override_config = load_override_config(args.config)

    result = call_transcriber_api(
        audio_file_path=args.audio_path,
        url=args.endpoint_url,
        override_config=override_config,
    )

    print("Resultado: ")
    print(result)

if __name__ == "__main__":
    main()
