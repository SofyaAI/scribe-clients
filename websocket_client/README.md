# WebSocket STT Client (Async / Real-Time)

Cliente de teste para o serviço de **Speech-to-Text (STT)** via WebSocket, simulando o comportamento de um **browser/microfone**.

Este cliente foi projetado para testes funcionais, validação de latência e **testes de carga**, utilizando envio de áudio em **tempo real**.

---

## Funcionalidades

- Envio de áudio em **tempo real** (browser-like)
- Controle de velocidade do envio (`pace_factor`)
- Envio automático de **silêncio após o fim do áudio** (útil para VAD / flush)
- Recepção de transcrições **parciais e finais**
- Encerramento automático por **idle timeout**
- Suporte a **múltiplos usuários simultâneos (load test)**
- Geração automática de arquivo `.txt` com a transcrição final
- Estatísticas de latência e tempo de sessão

---

## Preparar o ambiente

### 1. Criar e ativar o ambiente virtual

```bash
python -m venv .venv
source .venv/bin/activate  # Linux / macOS
# ou
.\.venv\Scripts\activate   # Windows
```

### 2. Instalar as dependências

```bash
pip install -r requirements.txt
```

Dependências principais:
- `websockets`
- `pandas`

---

## Áudio de exemplo

Utilize um arquivo WAV PCM, por exemplo:

```text
consulta.wav
```

> O cliente também suporta áudio bruto (`.pcm`, `.raw`), usando um *fallback* de bytes/s, mas WAV é altamente recomendado para simulação fiel de browser.

---

## Uso básico (1 usuário)

Executa uma sessão única, enviando o áudio em tempo real.

```bash
python stt_ws_test.py \
  --host-ws wss://<rota-stt>/ws/transcriber \
  --audio ./consulta.wav \
  --language portuguese
```

### Saída gerada

- Transcrição final salva como:

```text
consulta.user_1.txt
```

- Estatísticas de latência exibidas no console

---

## Parâmetros principais

| Parâmetro | Descrição | Default |
|---------|----------|---------|
| `--chunk-ms` | Duração de cada chunk em ms (simula microfone) | `20` |
| `--pace` | Velocidade do envio (`1.0 = tempo real`) | `1.0` |
| `--silence-after` | Segundos de silêncio após o fim do áudio | `2.0` |
| `--idle-timeout` | Tempo sem mensagens para encerrar recepção | `10` |
| `--language` | Idioma da transcrição | `portuguese` |

### Exemplo com parâmetros explícitos

```bash
python stt_ws_test.py \
  --host-ws wss://<rota-stt>/ws/transcriber \
  --audio ./consulta.wav \
  --chunk-ms 20 \
  --pace 1.0 \
  --silence-after 3 \
  --idle-timeout 15
```

---

## Teste de carga (múltiplos usuários)

Simula vários usuários enviando áudio **em paralelo**, cada um com sua própria conexão WebSocket.

```bash
python stt_ws_test.py \
  --host-ws wss://<rota-stt>/ws/transcriber \
  --audios ./audio1.wav,./audio2.wav,./audio3.wav \
  --users 10 \
  --idle-timeout 20
```

### Comportamento no modo carga

- Os áudios são utilizados em **round-robin**
- Cada usuário gera seu próprio arquivo `.txt`
- Um relatório agregado é exibido ao final:
  - Tempo médio de processamento do modelo
  - Tempo total de sessão
  - P95 de latência

---

## Exemplo de saída no console

```text
[user_1] (P) Bom dia, doutor...
[user_1] (F) Estou com dor abdominal há três dias.

[user_1] Latency Stats:
count    12.000
mean      0.184
min       0.102
max       0.331
```

---

## Observações importantes

- O cliente **não depende do fechamento imediato do WebSocket** para finalizar a transcrição  
  → o encerramento ocorre via **idle timeout**
- O envio de silêncio após o áudio ajuda a:
  - disparar flush do VAD
  - garantir o retorno do último segmento
- Por padrão, o texto final concatena **apenas mensagens finais** (`is_partial = false`)
  - Caso necessário, é possível concatenar tudo utilizando `--concat-tudo`

---

## Exemplo de uso em ambiente de produção

```bash
python stt_ws_test.py \
  --host-ws wss://stt.suaempresa.com/ws/transcriber \
  --audio ./consulta.wav \
  --language portuguese \
  --chunk-ms 20 \
  --pace 1.0 \
  --silence-after 2 \
  --idle-timeout 15
```
