import pytest
from sqlalchemy.exc import DatabaseError, OperationalError

from database import get_db
from main import app


def test_health(client):
    assert client.get("/health").json() == {"status": "ok", "database": "ok"}


def _base_coupee():
    raise OperationalError("SELECT secret FROM table_cachee", {}, Exception("ORA-03113: end-of-file"))
    yield


def _bug_sql():
    raise DatabaseError("SELECT secret FROM table_cachee", {}, Exception("ORA-00942: table or view does not exist"))
    yield


@pytest.mark.parametrize(("dependance", "statut"), [(_base_coupee, 503), (_bug_sql, 500)])
def test_erreurs_base_sans_fuite_sql(client, dependance, statut):
    app.dependency_overrides[get_db] = dependance
    reponse = client.get("/books")

    assert reponse.status_code == statut
    assert "ORA-" not in reponse.text and "SELECT" not in reponse.text


def test_cors(client):
    def preflight(origine):
        return client.options("/books", headers={"Origin": origine, "Access-Control-Request-Method": "GET"})

    assert preflight("http://localhost:3000").headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "access-control-allow-origin" not in preflight("https://site-inconnu.example").headers
