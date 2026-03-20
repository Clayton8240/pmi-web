# Estrutura da Etiqueta PDF

Este documento descreve a estrutura da etiqueta gerada em PDF pelo sistema.

## Visão Geral
A etiqueta PDF é utilizada para identificação de volumes, contendo informações essenciais para logística, rastreio e conferência de materiais.

## Layout Geral
- **Formato:** A4 (padrão), podendo ser ajustado conforme necessidade.
- **Orientação:** Retrato
- **Margens:** Configuradas para impressão sem cortes.

## Componentes da Etiqueta

### 1. Cabeçalho
- **Logo da empresa:**
  - Esquerda: `assets/logo_mentor.png`.
  - Direita: `assets/logo_pmi.png`.
  - Caso não existam, exibe texto alternativo.
- **Nome da empresa:** Centralizado, destacado.

### 2. Informações principais
- **Código do volume:**
  - Exemplo: `CD-0001-01`
  - Fonte grande, destaque visual.
- **Descrição do material:**
  - Nome do material ou lote.
- **Quantidade:**
  - Exemplo: `Qtd: 10`
- **Peso/Volume:**
  - Exemplo: `Volume: 0,25 m³`
- **Transportadora:**
  - Nome da transportadora responsável.

### 3. Informações secundárias
- **Data de geração:**
  - Exemplo: `Gerado em: 20/03/2026 14:30`
- **Usuário responsável:**
  - Nome do usuário que gerou a etiqueta (se disponível).

### 4. Código de barras (opcional)
- **Conteúdo:** Código do volume ou outro identificador único.
- **Formato:** Code128 ou similar.

### 5. Rodapé
- **Observações:**
  - Espaço para observações ou instruções adicionais.

## Observações
- O layout pode ser customizado via templates Jinja2 em `app/templates/etiquetas/`.
- Caso algum campo não esteja disponível, o sistema exibe um placeholder ou omite o campo.
- As imagens de logo são opcionais.

## Exemplo Visual (esquemático)

```
+------------------------------------------------------+
| [Logo Mentor]        Empresa XYZ        [Logo PMI]   |
|                                                      |
|                CÓDIGO: CD-0001-01                    |
|           Material: Caixa de Parafusos                |
|           Qtd: 10   Volume: 0,25 m³                  |
|           Transportadora: New Pratika                 |
|                                                      |
| Gerado em: 20/03/2026 14:30  Usuário: admin          |
|                                                      |
| [Código de Barras]                                   |
|                                                      |
| Observações:                                         |
| - Frágil                                             |
+------------------------------------------------------+
```

> Para customizações, edite os templates HTML em `app/templates/etiquetas/`.
