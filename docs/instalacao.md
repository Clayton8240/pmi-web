# Instalação e Configuração

## Pré-requisitos

- Python 3.12+
- PostgreSQL 14+
- pip / venv

## 1. Clonar o repositório

```bash
git clone https://github.com/Clayton8240/pmi-web.git
cd pmi-web
```

## 2. Criar ambiente virtual e instalar dependências

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 3. Banco de dados

### Criar usuário e banco

```sql
-- Executar como superusuário postgres
CREATE USER mentor WITH PASSWORD 'MM&Br4zil';
CREATE DATABASE pmi_etiquetas OWNER mentor;
```

### Restaurar estrutura

```bash
PGPASSWORD='MM&Br4zil' psql -U mentor -h localhost -d pmi_etiquetas -f dump_schema_only.sql
```

> O arquivo `dump_schema_only.sql` contém toda a DDL (tabelas, sequences, constraints) sem dados.

## 4. Variáveis de ambiente

Crie um arquivo `.env` na raiz do projeto:

```env
DATABASE_URL=postgresql://mentor:MM%26Br4zil@localhost/pmi_etiquetas
OUTPUT_FOLDER=etiquetas_geradas
EMPRESA_NOME=Mentor Brasil
TRANSPORTADORA_PADRAO=New Pratika Express Ltda
```

## 5. Logos (opcional)

Coloque os arquivos de logo na pasta `assets/`:

| Arquivo | Uso |
|---|---|
| `assets/logo_mentor.png` | Cabeçalho esquerdo da etiqueta |
| `assets/logo_pmi.png` | Cabeçalho direito da etiqueta |

Se os arquivos não existirem, o sistema usa texto como fallback automaticamente.

## 6. Iniciar o servidor

```bash
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Acesse: `http://localhost:8000`

## Docker (alternativa)

```bash
docker-compose up --build
```

---

## Deploy em produção (servidor Linux)

Para fazer deploy em um servidor Linux com nginx e PostgreSQL já instalados, sem Docker, consulte o guia completo em [deploy.md](deploy.md).

Resumo dos componentes:

| Componente | Detalhe |
|---|---|
| Código | `/opt/pmi-web` |
| Virtualenv | `/opt/pmi-web/.venv` |
| Processo | systemd `pmi-web.service` (uvicorn em `127.0.0.1:8100`) |
| Nginx | proxy reverso expondo a porta `8001` |
| URL | `http://192.168.38.234:8001` |

---

## Variáveis de ambiente disponíveis

| Variável | Padrão | Descrição |
|---|---|---|
| `DATABASE_URL` | `postgresql://mentor:MM%26Br4zil@localhost/pmi_etiquetas` | String de conexão PostgreSQL |
| `OUTPUT_FOLDER` | `etiquetas_geradas` | Pasta onde os PDFs de lote são salvos |
| `EMPRESA_NOME` | `Mentor Brasil` | Nome exibido em telas do sistema |
| `TRANSPORTADORA_PADRAO` | `New Pratika Express Ltda` | Pré-preenchimento do campo transportadora |
