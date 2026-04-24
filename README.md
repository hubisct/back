# Backend Vitrine HUBIS

API REST desenvolvida com **Flask**, **SQLAlchemy** e **SQLite**.

---

## Executando com Docker (recomendado)

Pré-requisito: ter o [Docker](https://docs.docker.com/get-docker/) instalado.

```bash
# Subir o container (build automático na primeira vez)
docker compose up --build

# Executar em segundo plano
docker compose up --build -d

# Parar o container
docker compose down
```

A API estará disponível em `http://localhost:5174`.

Na primeira execução, o banco de dados SQLite é criado e populado automaticamente com dados de exemplo (seed).

### Volumes persistentes

| Volume | Caminho no container | Descrição |
|---|---|---|
| `uploads_data` | `/app/uploads` | Imagens enviadas via upload |
| `db_data` | `/app/data` | Banco de dados SQLite |

Para resetar os dados, remova os volumes:

```bash
docker compose down -v
```

---

## Executando sem Docker

```bash
python -m venv venv
source venv/bin/activate   # Linux/macOS
venv\Scripts\activate      # Windows

pip install -r requirements.txt
python init_db.py
```

Resetar somente produtos (preserva empresas e usuarios):

```
python reset_products_only.py
```

Resetar e popular produtos fake novamente:

```
python reset_products_only.py --seed
```

Executar

```
python app.py
```

---

## Estrutura do projeto

```
├── app.py              # Aplicação Flask (rotas da API)
├── models.py           # Modelos SQLAlchemy (Enterprise, Product, User)
├── validators.py       # Validações (email, senha, telefone)
├── init_db.py          # Script de criação e seed do banco
├── seed_data.py        # Dados iniciais de exemplo
├── requirements.txt    # Dependências Python
├── Dockerfile          # Imagem Docker da aplicação
├── docker-compose.yml  # Orquestração do container
└── .dockerignore       # Arquivos ignorados no build Docker
```

## Endpoints principais

| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/health` | Health check |
| GET | `/api/categories` | Lista categorias |
| GET/POST | `/api/enterprises` | Listar / criar empreendimentos |
| GET/PUT/DELETE | `/api/enterprises/:id` | Detalhe / editar / remover empreendimento |
| POST | `/api/enterprises/:id/products` | Criar produto |
| PUT/DELETE | `/api/enterprises/:id/products/:pid` | Editar / remover produto |
| GET/POST | `/api/users` | Listar / criar usuários |
| POST | `/api/login` | Autenticação |
| POST | `/api/upload` | Upload de arquivo |
