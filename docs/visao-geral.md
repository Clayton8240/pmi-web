# Visão Geral

## O que é

O **PMI Etiquetas Web** é um sistema interno desenvolvido para a **Mentor Media** que automatiza a geração de etiquetas de remessa de materiais POSM (Point of Sale Materials) da **Philip Morris Media**.

Cada etiqueta identifica uma caixa expedida para um Centro de Distribuição (CD), contendo informações de rastreamento, destinatário, transportadora e lista detalhada dos itens embalados.

## Tecnologias

| Camada | Tecnologia |
|---|---|
| Backend | Python 3.12 + FastAPI + Uvicorn |
| ORM / Banco | SQLAlchemy 2.0 + PostgreSQL |
| Templates | Jinja2 + HTMX + TailwindCSS (CDN) |
| Geração de PDF | ReportLab |
| Leitura de planilha | openpyxl |

## Estrutura do projeto

```
pmi-web/
├── app/
│   ├── config.py          # Configurações via variáveis de ambiente
│   ├── database.py        # Conexão e Base SQLAlchemy
│   ├── main.py            # Entry-point FastAPI, monta routers
│   ├── models/            # Modelos ORM (Campanha, CD, ItemCD, Etiqueta, Material)
│   ├── routers/           # Rotas HTTP (etiquetas, cds, materiais, importacao, api)
│   ├── services/          # Regras de negócio (pdf_service, importacao, volume_calc)
│   └── templates/         # HTML Jinja2 por módulo
├── assets/                # Logos (não versionados)
├── static/css/            # CSS customizado
├── etiquetas_geradas/     # PDFs de lote gerados (não versionados)
├── docs/                  # Esta documentação
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── .env                   # Variáveis de ambiente (não versionado)
```

## Módulos principais

### Campanhas
Cada ciclo de distribuição é uma **Campanha** (ex.: `PMI Q1 2026`). A campanha agrupa os CDs participantes e os materiais a enviar.

### CDs (Centros de Distribuição)
Importados via planilha Excel. Cada CD possui um **Controle MMBR** (ID numérico único), regional, filial, cidade/UF e zona de venda.

### Etiquetas
Geradas em lote para todos os CDs de uma campanha. Cada etiqueta corresponde a uma caixa física expedida. Os PDFs individuais são gerados sob demanda (não são salvos em disco); apenas o **PDF de lote** é persistido por 30 dias.

### Histórico e Reimpressão
Cada geração fica registrada no banco. É possível reimprimir qualquer etiqueta a qualquer momento — o PDF é regenerado a partir dos dados do banco sem necessidade de arquivo salvo.

