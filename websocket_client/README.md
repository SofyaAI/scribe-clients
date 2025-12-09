# websocket client

## Preparar o ambiente

- Criar e ativar o ambiente virtual manualmente (sem makefile):

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# ou
.\.venv\Scripts\activate   # Windows
```

- Instalar as dependências:

```bash
pip install -r requirements.txt
```

## Áudio de exemplo

- Utilize o arquivo `consulta.wav` como áudio de teste.

## Como usar

Com o ambiente virtual ativado, execute:

```bash
python run.py wss://<rota-stt>/ws/transcriber ./consulta.wav
```

Substitua `<rota-stt>` pela rota WebSocket do serviço de STT fornecida pelo time.

