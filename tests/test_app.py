import os
import tempfile
import pytest

# configurar variáveis de ambiente necessárias antes de importar o app
temp_dir = tempfile.TemporaryDirectory()
os.environ["DATA_DIR"] = temp_dir.name
os.environ["JWT_SECRET"] = "test-secret-key-12345-super-long-key-for-jwt-security-compliance"

from app import app, engine as app_engine
from init_db import init_db, engine as init_db_engine

@pytest.fixture(scope="session", autouse=True)
def setup_database():
    # inicializa as tabelas e insere dados de exemplo (seed) sem tentar excluir o arquivo
    init_db(drop=False)
    yield
    # encerra as conexões do SQLAlchemy para liberar os locks no arquivo SQLite
    app_engine.dispose()
    init_db_engine.dispose()
    try:
        temp_dir.cleanup()
    except Exception:
        pass

@pytest.fixture
def client():
    with app.test_client() as client:
        yield client

def test_health_check(client):
    # testar se o endpoint de health check funciona e retorna o status esperado
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}

def test_protected_route_without_token(client):
    # testar se uma rota protegida retorna 401 sem token no cabeçalho
    response = client.get("/api/users")
    assert response.status_code == 401

def test_login_success(client):
    # testar se o login do administrador de exemplo funciona
    payload = {
        "email": "admin@hubis.ufsm.br",
        "password": "senhaadmin"
    }
    response = client.post("/api/login", json=payload)
    assert response.status_code == 200
    data = response.get_json()
    assert data["email"] == "admin@hubis.ufsm.br"
    assert data["role"] == "admin"
    assert "token" in data

def test_login_invalid_password(client):
    # testar se o login com senha incorreta retorna 401
    payload = {
        "email": "admin@hubis.ufsm.br",
        "password": "senhaerrada123"
    }
    response = client.post("/api/login", json=payload)
    assert response.status_code == 401
    assert response.get_json() == {"ok": False}

def test_access_protected_route_with_valid_token(client):
    # testar o fluxo completo: login, obtenção do token e acesso a rota protegida
    login_payload = {
        "email": "admin@hubis.ufsm.br",
        "password": "senhaadmin"
    }
    login_res = client.post("/api/login", json=login_payload)
    token = login_res.get_json()["token"]

    # usar o token para acessar a lista de usuários
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/api/users", headers=headers)
    assert response.status_code == 200
    users = response.get_json()
    assert len(users) > 0
    # verificar se o administrador está presente na lista
    emails = [u["email"] for u in users]
    assert "admin@hubis.ufsm.br" in emails
