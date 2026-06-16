## Como Rodar os Testes

Certifique que o ambiente virtual está instalado

### Windows:
```powershell
# Rodar todos os testes
.\venv\Scripts\pytest
```

### No Linux / macOS:
```bash
# Rodar todos os testes
./venv/bin/pytest
```

---

## Estrutura de Testes

Os testes estão organizados dentro do diretório `/tests`:

* **`tests/test_validators.py`**: Testes unitários para as funções de validação de dados em `validators.py` (emails, senhas, telefones e imagens base64).
* **`tests/test_app.py`**: Testes de integração para as rotas do Flask em `app.py` (como `/api/health`, `/api/login` e `/api/users`), utilizando um banco de dados SQLite temporário em memória para cada sessão de teste.

---

## Configurações

O arquivo `pytest.ini` na raiz do projeto está configurado para:
1. Incluir a raiz do projeto no `pythonpath`, permitindo as importações dos módulos.
2. Ocultar avisos de depreciação (`DeprecationWarning`) gerados por bibliotecas de terceiros, mantendo a saída de testes limpa.
