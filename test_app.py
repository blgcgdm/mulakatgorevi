import os
import tempfile

# app.py import edilmeden ONCE ayarlanmali: gercek mulakat.db'ye dokunulmaz.
os.environ["DB_PATH"] = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ["ADMIN_API_KEY"] = "test-key"

import pytest
from fastapi.testclient import TestClient

from app import app

KEY = {"x-api-key": "test-key"}


@pytest.fixture(scope="module")
def client():
    # with bloku lifespan'i calistirir (tablolar ve seed verisi olusur)
    with TestClient(app) as c:
        yield c


# ---------- Auth ----------

def test_all_data_anahtarsiz_401(client):
    assert client.get("/all_data").status_code == 401


def test_all_data_yanlis_anahtar_401(client):
    r = client.get("/all_data", headers={"x-api-key": "yanlis"})
    assert r.status_code == 401


def test_all_data_dogru_anahtar_200(client):
    r = client.get("/all_data", headers=KEY)
    assert r.status_code == 200
    assert any(row[1] == "admin" for row in r.json())


def test_all_data_filtre(client):
    r = client.get("/all_data", params={"filter_text": "admin"}, headers=KEY)
    assert r.status_code == 200
    assert len(r.json()) >= 1
    assert all("admin" in (row[1] + row[2]) for row in r.json())


def test_export_anahtarsiz_401(client):
    assert client.get("/export").status_code == 401


def test_export_dogru_anahtar_200(client):
    r = client.get("/export", headers=KEY)
    assert r.status_code == 200
    assert r.json()["count"] >= 2


# ---------- Herkese acik endpoint'ler ----------

def test_feed_post_ve_yorumlar(client):
    r = client.get("/feed")
    assert r.status_code == 200
    data = r.json()
    assert len(data) >= 1
    assert len(data[0]["comments"]) == 2


def test_user_search_sadece_id_ve_name(client):
    r = client.get("/user_search", params={"name": "admin"})
    assert r.status_code == 200
    assert r.json() == [[1, "admin"]]


# ---------- Kullanici olusturma ----------

def test_kullanici_olustur_ve_ayni_eposta_409(client):
    body = {"name": "veli", "email": "veli@test.com"}
    assert client.post("/users", json=body).status_code == 200
    assert client.post("/users", json=body).status_code == 409


def test_bos_isim_422(client):
    r = client.post("/users", json={"name": "", "email": "a@b.com"})
    assert r.status_code == 422


def test_gecersiz_eposta_422(client):
    r = client.post("/users", json={"name": "x", "email": "abc"})
    assert r.status_code == 422
