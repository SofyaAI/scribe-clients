# batch-clients

Cliente Python simples para chamar um endpoint de transcrição de áudio (`/api/transcriber`), com suporte a:

- Envio de arquivo de áudio via `multipart/form-data`.
- Envio opcional de um objeto `override_config` em JSON (campo de formulário).

Este README assume o script principal chamado `run.py`.

---

## 1. Requisitos

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
---

## 2. Arquivo principal (`run.py`)

**Parâmetros:**

- `audio_file_path`: caminho local para o arquivo de áudio (ex.: `meu_audio.wav`).
- `url`: URL completa do endpoint (ex.: `https://host/api/transcriber`).
- `confg` (opcional): dicionário Python com a configuração de override.
  - Se **não** for passado, **nenhum** campo `config` será enviado e o backend usará a configuração padrão dele.

**Retorno:**

- Dicionário com o JSON retornado pela API

---

## 3. Uso via linha de comando (CLI)

O script pode ser chamado diretamente via terminal.

### 3.1. Exemplo básico (sem override_config)

```bash
python run.py   meu_audio.wav   --endpoint-url "https://qigl42xisv7ch4-8000.proxy.runpod.net/api/transcriber"
```

Nesse caso, **nenhum** `override_config` será enviado, e o servidor usará a configuração padrão dele.

### 3.2. Usando um arquivo de configuração JSON

Crie um arquivo, por exemplo `config.json`, com ajuda do time Sofya:

Rode:

```bash
python run.py   meu_audio.wav   --endpoint-url "https://qigl42xisv7ch4-8000.proxy.runpod.net/api/transcriber"   --config config.json
```

### 3.3. Passando o JSON inline

Você também pode passar o JSON diretamente na linha de comando:

```bash
python run.py   meu_audio.wav   --endpoint-url "https://qigl42xisv7ch4-8000.proxy.runpod.net/api/transcriber"   --config 'CONTEUDO JSON'
```

> 💡 Em shells Unix, use aspas simples `'...'` em volta do JSON para evitar que caracteres especiais sejam interpretados pelo shell.