# Estrutura do Banco de Dados

Banco: `pmi_etiquetas`  
Usuário: `mentor`  
ORM: SQLAlchemy 2.0 (mapeamento declarativo)

---

## Diagrama de relacionamentos

```
campanhas ──┬── itens_cd ────── cds
            │      └─────────── materiais ── volumes_caixa
            └── etiquetas ───── itens_etiqueta
```

---

## Tabelas

### `campanhas`
Representa um ciclo/rodada de distribuição.

| Coluna | Tipo | Descrição |
|---|---|---|
| `id` | SERIAL PK | Identificador interno |
| `nome` | VARCHAR(200) | Nome da campanha (ex.: `PMI Q1 2026`) |
| `criada_em` | TIMESTAMP | Data de criação |
| `status` | VARCHAR(20) | `ativa` ou `encerrada` |

---

### `cds`
Centros de Distribuição importados via planilha.

| Coluna | Tipo | Descrição |
|---|---|---|
| `id` | INTEGER PK | **Controle MMBR** (vem da coluna da planilha) |
| `cnpj` | VARCHAR(20) | CNPJ do CD |
| `cidade` | VARCHAR(100) | Cidade |
| `uf` | VARCHAR(2) | Estado |
| `regional` | VARCHAR(100) | Nome da regional |
| `filial` | VARCHAR(150) | Nome da filial |
| `zona_venda` | VARCHAR(150) | Zona de venda / descrição do pacote |
| `descricao_pacote` | TEXT | Descrição da campanha (coluna G da planilha) |
| `ativo` | BOOLEAN | Se o CD está ativo |
| `importado_em` | TIMESTAMP | Data da importação |

---

### `materiais`
Catálogo de materiais POSM.

| Coluna | Tipo | Descrição |
|---|---|---|
| `id` | SERIAL PK | Identificador interno |
| `part_number` | VARCHAR(50) UNIQUE | Código do material (ex.: `POSM-001`) |
| `descricao` | VARCHAR(255) | Descrição do material |
| `marca` | VARCHAR(100) | Marca (Marlboro, Bond Street, etc.) |
| `unidade` | VARCHAR(20) | Unidade de medida (padrão: `UN`) |
| `ativo` | BOOLEAN | Se o material está ativo |
| `criado_em` | TIMESTAMP | Data de criação |

---

### `volumes_caixa`
Configuração de embalagem por caixa para um material.

| Coluna | Tipo | Descrição |
|---|---|---|
| `id` | SERIAL PK | Identificador interno |
| `material_id` | FK → materiais | Material relacionado |
| `descricao` | VARCHAR(100) | Texto na etiqueta (ex.: `10UN/CX`) |
| `qtde_por_cx` | INTEGER | Quantidade de unidades por caixa |
| `ativo` | BOOLEAN | Se a configuração está ativa |

---

### `itens_cd`
Itens de material destinados a um CD dentro de uma campanha. Populado na importação da planilha.

| Coluna | Tipo | Descrição |
|---|---|---|
| `id` | SERIAL PK | Identificador interno |
| `campanha_id` | FK → campanhas | Campanha à qual pertence |
| `cd_id` | FK → cds | CD de destino |
| `material_id` | FK → materiais (nullable) | Referência ao catálogo de materiais |
| `part_number` | VARCHAR(50) | Código do material (desnormalizado para velocidade) |
| `marca` | VARCHAR(100) | Marca (desnormalizado) |
| `descricao` | VARCHAR(255) | Descrição (desnormalizado) |
| `qtde` | INTEGER | Quantidade de unidades a enviar |

---

### `etiquetas`
Histórico de etiquetas geradas. Um registro por caixa impressa.

| Coluna | Tipo | Descrição |
|---|---|---|
| `id` | SERIAL PK | Identificador interno |
| `campanha_id` | FK → campanhas | Campanha relacionada |
| `cd_id` | FK → cds | CD de destino |
| `num_caixa` | INTEGER | Número sequencial da caixa no lote |
| `volume` | VARCHAR(255) | Volume impresso (ex.: `1/3`) |
| `embalagem` | VARCHAR(100) | Tipo de embalagem (ex.: `CAIXA`) |
| `projeto` | VARCHAR(100) | Nome do projeto impresso na etiqueta |
| `transportador` | VARCHAR(200) | Transportadora |
| `pdf_path` | VARCHAR(500) | Caminho do PDF de lote (`NULL` para individuais) |
| `gerada_em` | TIMESTAMP | Data e hora da geração |
| `reimpressao` | BOOLEAN | `true` se for reimpressão (carimbo vermelho no PDF) |

**Índices:** `ix_etiquetas_campanha_id`, `ix_etiquetas_num_caixa`

---

### `itens_etiqueta`
Snapshot dos itens impressos em cada etiqueta. Garante que a reimpressão reproduz exatamente o conteúdo original, mesmo que o catálogo seja alterado depois.

| Coluna | Tipo | Descrição |
|---|---|---|
| `id` | SERIAL PK | Identificador interno |
| `etiqueta_id` | FK → etiquetas | Etiqueta à qual pertence |
| `part_number` | VARCHAR(50) | Código do material no momento da impressão |
| `marca` | VARCHAR(100) | Marca no momento da impressão |
| `descricao` | VARCHAR(255) | Descrição no momento da impressão |
| `qtde` | INTEGER | Quantidade impressa |
