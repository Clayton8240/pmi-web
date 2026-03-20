# Fluxo de Uso

## 1. Importar planilha e criar campanha

Acesse **Importação** (`/importacao`).

1. Selecione o arquivo Excel (`.xlsx`) fornecido pela PMI.
2. O sistema detecta automaticamente o nome da campanha na coluna G.
3. Clique em **Importar** — o sistema cria a campanha, cadastra os CDs e os itens de cada CD em uma única operação.

> A planilha deve seguir o formato padrão PMI. Colunas esperadas: Ctrl MMBR, Regional, Filial, Cidade, UF, Zona de Venda, Nome da Campanha (coluna G), materiais e quantidades nas colunas seguintes.

---

## 2. Revisar CDs e itens

Acesse **CDs** (`/cds`) para visualizar os centros de distribuição importados, seus itens e volumes calculados por caixa.

---

## 3. Gerar lote de etiquetas

Acesse **Gerar Lote** (`/etiquetas/lote`).

1. A campanha ativa é selecionada automaticamente. É possível trocar de campanha pelo seletor no topo.
2. Preencha (ou confirme) os campos:
   - **Projeto / Campanha** — pré-preenchido com o nome da campanha
   - **Embalagem** — ex.: `CAIXA`
   - **Transportadora** — pré-preenchida com o padrão configurado
3. Clique em **Gerar Lote Completo**.
4. O sistema gera todas as etiquetas (uma por caixa de cada CD), registra no banco e produz um único **PDF de lote** para impressão.
5. O resultado aparece no topo da página com os botões **Imprimir** e **Baixar PDF**.

### Ordenação
As etiquetas são geradas na ordem do **Ctrl MMBR** (ID do CD), seguindo a sequência do processo de produção.

### Numeração
O contador de caixa começa **sempre em 1** a cada nova geração de lote.

---

## 4. Imprimir

- **Imprimir** — abre o PDF diretamente no navegador para impressão.
- **Baixar PDF** — faz o download do arquivo de lote.

Cada página do PDF corresponde a uma etiqueta (uma caixa).

---

## 5. Histórico e Reimpressão

Acesse **Histórico** (`/etiquetas/historico`).

- Todas as etiquetas geradas ficam registradas.
- Clique em **Reimprimir** em qualquer etiqueta para gerar o PDF individual sob demanda (regenerado a partir dos dados do banco — sem necessidade de arquivo salvo em disco).
- Uma reimpressão fica marcada com o carimbo `*** REIMPRESSÃO ***` em vermelho no PDF.

---

## Gestão de espaço em disco

- **PDFs individuais**: nunca são salvos em disco. Gerados em memória e entregues diretamente ao navegador.
- **PDFs de lote** (`LOTE_*.pdf`): salvos na pasta `etiquetas_geradas/` e removidos automaticamente após **30 dias** na próxima geração de lote.
