# 🏢 Sistema de Suporte à Decisão — NextByte

![Python](https://img.shields.io/badge/Python-3.13-blue)
![Grade](https://img.shields.io/badge/Grade-17%2F20-brightgreen)
![Status](https://img.shields.io/badge/Status-Done-brightgreen)
![License](https://img.shields.io/badge/License-Academic-lightgrey)

> **Engenharia de Sistemas de Dados** | Mestrado em Inteligência Artificial | Universidade do Minho | 2025/26

Conceção, arquitetura e implementação de um Data Warehouse centralizado para a **NextByte**, uma empresa de retalho tecnológico, integrando fontes heterogéneas (PostgreSQL, CSV e MongoDB/JSON) e enriquecendo perfis de clientes com análise de sentimentos via NLP.

---

## 📋 Descrição

O sistema integra dados de **vendas online** (PostgreSQL), **vendas físicas** históricas (CSV) e **reviews de clientes** (MongoDB → JSON) num Data Warehouse dimensional em **esquema de constelação** (Kimball), composto por dois Data Marts:

| Data Mart | Foco | Métricas |
|---|---|---|
| **Gestão de Vendas** | Desempenho comercial | Quantidade, PrecoUnitario |
| **Análise de Reviews** | Voz do cliente | Polaridade (−1 a 1), Estrelas |

### Funcionalidades

- Pipeline **ETL incremental** semanal com zonas de estágio, conciliação de fontes e quarentena automática.
- **SCD tipo 4** para rastreabilidade histórica dos clientes (DimCliente + DimClienteHistorico).
- **Análise de sentimentos** — polaridade, emoções e termos frequentes via VADER e NRClex.
- **Tabelas de lookup** para resolução de identidades entre fontes heterogéneas.
- **6 dashboards** interativos em Metabase (RSD1–RSD6): análise geográfica, segmentação por faixa etária, termos frequentes, emoções em feedback negativo, comparativo físico vs. online e evolução temporal da polaridade.

---

## 🏗️ Arquitetura

```
EXTRAÇÃO                 TRANSFORMAÇÃO               ARMAZENAMENTO          VISUALIZAÇÃO
┌───────────────┐     ┌──────────────────────┐     ┌──────────────┐     ┌──────────────┐
│ PostgreSQL    │────▶│                      │     │              │     │              │
│ (vendas)      │     │  Normalização        │     │    Data      │     │   Metabase   │
│               │     │  NLP (Python)        │────▶│  Warehouse   │────▶│  Dashboards  │
│ CSV (físicas) │────▶│  Qualidade           │     │ (PostgreSQL) │     │   & KPIs     │
│               │     │  Quarentena          │     │              │     │              │
│ MongoDB       │────▶│                      │     │              │     │              │
│ (reviews)     │     └──────────────────────┘     └──────────────┘     └──────────────┘
└───────────────┘
```

---

## 📁 Estrutura do Repositório

```
ESD/
├── data/
│   └── sources/                  # Ficheiros de dados fonte
│       ├── vendas_fisicas.csv    #   Histórico de vendas em loja
│       └── reviews.json          #   Reviews exportadas do MongoDB
├── database/
│   ├── sources/                  # Schema OLTP (fonte relacional)
│   │   ├── oltp_schema.sql
│   │   └── oltp_seed.sql
│   └── dw/                       # Schema do Data Warehouse
│       └── dw_schema.sql
├── docker/                       # Docker Compose por serviço
│   ├── oltp/                     #   PostgreSQL (vendas online)
│   ├── mongodb/                  #   MongoDB (reviews)
│   └── dw/                       #   PostgreSQL (Data Warehouse)
├── docs/                         # Documentação
│   ├── relatorio.pdf
│   └── enunciado.pdf
├── notebooks/                    # Notebooks exploratórios
├── src/
│   ├── etl/
│   │   ├── extratores/           #   Extração: SQL, CSV, MongoDB
│   │   ├── transforms/           #   Transformação + NLP
│   │   └── loaders/              #   Carga no DW
│   ├── utils/                    #   Lookup manager, helpers
│   └── main_etl.py               #   Orquestrador do pipeline
├── .gitignore
├── LICENSE
└── README.md
```

---

## 🚀 Utilização

### 1. Levantar as bases de dados

```bash
# OLTP (PostgreSQL com dados de vendas online)
cd docker/oltp && docker compose up -d

# MongoDB (reviews)
cd docker/mongodb && docker compose up -d

# Data Warehouse
cd docker/dw && docker compose up -d
```

### 2. Executar o pipeline ETL

```bash
cd src
python main_etl.py
```

---

## 🛠️ Stack Tecnológica

| Componente | Tecnologia |
|---|---|
| Linguagem | Python 3.13 |
| Bases de Dados | PostgreSQL, MongoDB |
| ETL | Pandas, psycopg2, pymongo |
| NLP | NLTK, VADER, NRClex |
| Visualização | Metabase |
| Infraestrutura | Docker Compose |
| Modelação | Indyco Builder, MySQL Workbench, Bizagi |

---

## 📊 Modelo Dimensional

**Esquema em Constelação** — 7 dimensões, 2 tabelas de factos:

| Dimensão | Tipo | Descrição |
|---|---|---|
| DimCliente | Conforme + SCD4 | Dados demográficos com tabela de histórico |
| DimProduto | Conforme | Catálogo: marca, categoria, subcategoria |
| DimCalendário | Conforme | Hierarquia: Data → Mês → Trimestre → Ano |
| DimZona | Conforme | Localização geográfica por distrito |
| DimFeedback | Regular | Top 3 termos e emoções extraídos por NLP |
| DimVenda | Degenerada | Identificador da transação |
| DimFonte | Degenerada | Origem: física (1) ou online (0) |

---

## 👥 Equipa

| Nome | Nº |
|---|---|
| Luís Silva | PG60390 |
| Guilherme Pinto | PG60225 |
| João Azevedo | PG61693 |
| Pedro Reis | PG59908 |
