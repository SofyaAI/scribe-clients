# scribe-clients

Este repositório contém **clientes Python de exemplo** para serviços de transcrição de áudio da Sofya, em dois modos de uso:

- **Batch (HTTP)** – envio de arquivo de áudio para o endpoint REST `/api/transcriber`.
- **Tempo real (WebSocket)** – envio de áudio via WebSocket para o endpoint `/ws/transcriber`.

Cada cliente possui seu próprio `README` com detalhes de uso.

---

## Estrutura do repositório

```text
scribe-clients/
├── batch_client/
│   ├── run.py
│   ├── requirements.txt
│   └── README.md        # instruções específicas do cliente batch (HTTP)
├── websocket_client/
│   ├── run.py
│   ├── requirements.txt
│   └── README.md        # instruções específicas do cliente WebSocket (tempo real)