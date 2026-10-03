# Alaz Takımı Görev #2: Kaynak Kod Analizi, İyileştirme ve Teknik Rapor

FastAPI + SQLite ile yazılmış kullanıcı / gönderi / yorum API'sinin güvenlik, mantık ve performans açısından
incelenmesi, düzeltilmesi ve doğrulanması.

## İçindekiler
1. [Kurulum ve çalıştırma](#kurulum-ve-çalıştırma)
2. [Depo yapısı](#depo-yapısı)
3. [Tespit edilen problemler](#tespit-edilen-problemler)
4. [Uygulanan çözümler ve mimari gerekçeler](#uygulanan-çözümler-ve-mimari-gerekçeler)
5. [Doğrulama: testler ve sonuçlar](#doğrulama-testler-ve-sonuçlar)
6. [Bilerek açık bırakılan noktalar](#bilerek-açık-bırakılan-noktalar)
7. [Notlar](#notlar)

## Kurulum ve çalıştırma

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

ADMIN_API_KEY=gizli123 python3 app.py
```

- Sunucu `http://127.0.0.1:8000` adresinde açılır, etkileşimli dokümantasyon `/docs` altındadır.
- `ADMIN_API_KEY` ayarlı değilse korumalı endpoint'ler her zaman `401` döner (güvenli varsayılan).
- Veritabanı yolu `DB_PATH` ortam değişkeniyle değiştirilebilir (varsayılan `mulakat.db`).

## Depo yapısı

```
app.py            Uygulama
test_app.py       pytest testleri (geçici veritabanı kullanır)
requirements.txt  Bağımlılıklar
.gitignore        mulakat.db, venv, __pycache__ vb.
README.md         Bu rapor
```

## Tespit edilen problemler

Önem: **Kritik** (veri sızıntısı / yetki / enjeksiyon), **Yüksek** (servis erişilebilirliği), **Orta**, **Düşük**.

| # | Nerede | Problem | Neden / risk | Önem |
|---|---|---|---|---|
| 1 | `POST /users` | `INSERT` sorgusu f-string ile kullanıcı girdisinden kuruluyor | SQL injection. Örneğin `name` alanına `x', 'y', 1) --` benzeri bir değer sorgunun yapısını değiştirebilir. | Kritik |
| 2 | `GET /user_search` | `WHERE name='{name}'` f-string | SQL injection. `?name=' OR '1'='1` tüm kullanıcıları döndürür, `UNION` ile başka tablolardan veri çekilebilir. (`sqlite3.execute` tek ifade çalıştırdığı için `;` ile ikinci komut eklenemez, ama veri sızdırmak için yine yeterlidir.) | Kritik |
| 3 | `POST /users` | `is_admin` değeri istemciden alınıyor (`data.get("is_admin", 0)`) | Mass assignment / yetki yükseltme: herkes kendini admin olarak kaydedebilir. | Kritik |
| 4 | `GET /all_data`, `GET /export` | Kimlik doğrulama yok, `is_admin` alanı hiçbir yerde kullanılmıyor | Tüm kullanıcıların e-postaları ve admin bilgisi herkese açık (veri sızıntısı). | Kritik |
| 5 | `GET /user_search` | `SELECT *` | Aranan kullanıcının e-postası ve `is_admin` değeri de dönüyor (gereğinden fazla veri). | Yüksek |
| 6 | `GET /feed` | `async def` içinde `time.sleep(1.5)` | Senkron uyku olay döngüsünü bloklar. Tek bir `/feed` isteği sırasında **tüm** endpoint'ler 1.5 sn donar, birkaç eşzamanlı istek servisi fiilen kilitler (DoS). | Yüksek |
| 7 | `GET /export` | `for i in range(5000)` içinde döngüyle string birleştirme | Kullanıcı sayısı arttıkça CPU ve bellek kullanımı katlanarak artar, anlamsız iş yapar (sonuç sadece uzunluk), olay döngüsünü bloklar. Kimlik doğrulaması da olmadığı için herkes tetikleyebilir. | Yüksek |
| 8 | `GET /feed` | N+1 sorgu: her gönderi için ayrı yorum sorgusu | Gönderi sayısıyla doğrusal artan sorgu sayısı. Sayfalama da yok, tüm tablo dönüyor. | Orta |
| 9 | `GET /all_data` | Tüm tabloyu çekip Python'da `str(row)` içinde arama, sayfalama yok | Bellek ve CPU israfı. Ayrıca `str(row)` içinde arama, istenmeyen sütunlarda da eşleşir. | Orta |
| 10 | `POST /users` | Girdi doğrulama yok (`req.json()`, `data["name"]`) | Eksik alan `KeyError` ile `500` döner, tip ve uzunluk kontrolü yok. | Orta |
| 11 | `users.email` | `UNIQUE` kısıt yok | Aynı e-posta ile sınırsız kayıt. | Orta |
| 12 | Global `cur` | Tüm istekler tek global cursor'ı paylaşıyor, hiç kapatılmıyor | Şu anki kodda `await` noktaları sonuçları bozmasa da kırılgan bir yapı: iş parçacığı ya da `await` eklendiği anda sonuçlar karışır. Kaynak yönetimi yok. | Orta |
| 13 | Modül seviyesi | Tablo oluşturma ve seed verisi import anında çalışıyor | Yan etkili import (testte ve araçlarda `import app` bile veritabanına yazar). Uygulama yaşam döngüsüne bağlı değil. | Düşük |
| 14 | `posts.user_id`, `comments.post_id` | Index yok | Büyük tablolarda yorum ve gönderi sorguları tam tablo taraması yapar. | Düşük |
| 15 | `__main__` | `host="0.0.0.0"` | Geliştirme servisi tüm ağ arayüzlerine açık. | Orta |
| 16 | Genel | `temp_state`, `import time` (sleep kalkınca gereksiz), anlamsız `req_count` | Hiç okunmayan global durum. Çok işçili (multi-worker) çalışmada süreç başına farklı sayaç olacağı için anlamsız. | Düşük |
| 17 | Depo | `.gitignore`, `requirements.txt`, test yok | Veritabanı dosyası repoya girebilir, kurulum ve doğrulama tekrarlanamaz. | Düşük |

### SQL injection incelemesi: `/feed`

Orijinalde `f"... post_id={p[0]}"` kullanılıyordu. `p[0]` kullanıcı girdisi değil, veritabanından gelen tamsayı olduğu için
doğrudan sömürülebilir değildi, ama kötü bir kalıp olduğu için kaldırıldı. Yeni sürümde `IN ({placeholders})` ifadesine
**sadece `?` karakterleri** ekleniyor, değerler ayrıca parametre olarak veriliyor. Yani f-string içinde kullanıcı girdisi yok, güvenli.

## Uygulanan çözümler ve mimari gerekçeler

| Problem # | Çözüm | Gerekçe |
|---|---|---|
| 1, 2 | Tüm sorgular parametreli (`?`) | Değerler sorgu metninden ayrı gönderilir, veritabanı bunları asla SQL olarak yorumlamaz. Standart ve en etkili savunma. |
| 3 | `is_admin` istemciden alınmıyor, kayıt her zaman `0` ile oluşuyor. Pydantic modeli (`UserIn`) sadece `name` ve `email` kabul ediyor | Yetki alanları sunucu tarafında belirlenir, istemci girdisine güvenilmez. |
| 4 | `/all_data` ve `/export` için `x-api-key` başlığı ile `Depends(require_admin)`. Anahtar ortam değişkeninden okunuyor, karşılaştırma `secrets.compare_digest` ile yapılıyor, anahtar tanımlı değilse hep `401` | Sır kod içinde tutulmaz. Sabit zamanlı karşılaştırma zamanlama saldırısını önler. Ayarlanmamış anahtar güvenli tarafta kalır (kapalı). |
| 5 | `SELECT id, name` | En az veri ilkesi. |
| 6 | `time.sleep` kaldırıldı | Bloklayıcı çağrı olay döngüsünü dondurduğu için gerekçesi olmayan gecikme tamamen silindi. |
| 7 | Döngü kaldırıldı, `SELECT COUNT(*)` ile sayı dönüyor, endpoint korumalı | İş tek bir sorguya indi. **Not:** yanıt alanı `length` yerine `count` oldu (anlamlı bir değer döndürmek için). Bu bir API sözleşmesi değişikliğidir. |
| 8 | Gönderiler `LIMIT/OFFSET` ile sayfalı (`limit` 1-100'e sınırlı), yorumlar tek `IN (...)` sorgusuyla toplu çekiliyor | N+1 yerine her sayfa için 2 sorgu. Boş gönderi listesinde ikinci sorgu çalıştırılmıyor (SQLite boş `IN ()` kabul eder ama MySQL/PostgreSQL etmez ve gereksiz sorgu). |
| 9 | Filtre SQL'de (`name LIKE ? OR email LIKE ?`), `LIMIT/OFFSET`, sadece gerekli sütunlar, `limit` 1-200'e sınırlı | Filtreleme ve sayfalama veritabanında yapılır, bellek kullanımı sabit kalır. |
| 10 | Pydantic `Field(min_length, max_length)` ve basit e-posta kontrolü | Hatalı girdi `500` yerine `422` döner. |
| 11 | `email TEXT UNIQUE`, `IntegrityError` yakalanıp `409` dönülüyor | Kısıt veritabanında olduğu için eşzamanlı isteklerde de garanti sağlar (önce `SELECT` sonra `INSERT` yarış durumuna açıktır). |
| 12 | Her istekte yeni cursor, `try/finally` ile kapatma | Cursor'lar istekler arasında paylaşılmaz, kaynak sızıntısı olmaz. |
| 13 | `lifespan` içinde `init_db()`, kapanışta bağlantı kapatma | Kurulum uygulama başlangıcına bağlanır, import yan etkisiz olur. |
| 14 | `CREATE INDEX IF NOT EXISTS` (iki index) | `WHERE` ve `IN` sorguları index kullanır. |
| 15 | `127.0.0.1` | Servis yalnızca yerel makineden erişilebilir. Dışarı açılacaksa ters vekil sunucu arkasında bilinçli bir kararla yapılmalı. |
| 16 | Kullanılmayan kodlar kaldırıldı | Okunabilirlik. |
| 17 | `.gitignore`, `requirements.txt`, `test_app.py` eklendi | Tekrarlanabilir kurulum ve doğrulama. |

### Geliştirme sırasında öğrenilen: `UNIQUE` eski veritabanında etki etmez

`CREATE TABLE IF NOT EXISTS`, tablo zaten varsa hiçbir şey yapmaz. Bu yüzden `UNIQUE` kısıtını eklediğimde mevcut
`mulakat.db` dosyasında etkisi olmadı ve yeniden kayıt hâlâ başarılı oldu. Geliştirme ortamında dosyayı silip yeniden
oluşturarak doğruladım. Gerçek bir ortamda bunun için migration (örneğin Alembic) gerekir.

## Doğrulama: testler ve sonuçlar

### Otomatik testler

```bash
pytest
```

Testler `DB_PATH` ile geçici bir veritabanı kullanır, `mulakat.db` dosyasına dokunmaz.

**Sonuç:** `11 passed in 1.02s`

### Elle testler (Swagger `/docs`, `ADMIN_API_KEY=gizli123`)

Sunucu günlüğündeki durum kodlarından alınmıştır.

| Test | Beklenen | Gözlenen |
|---|---|---|
| `GET /all_data`, anahtarsız | 401 | 401 |
| `GET /all_data`, doğru anahtar | 200 | 200 |
| `GET /all_data?filter_text=admin`, doğru anahtar | 200 | 200 |
| `GET /export`, anahtarsız ve yanlış anahtar | 401 | 401, 401 |
| `GET /export`, doğru anahtar | 200 | 200 |
| `GET /feed` | 200 | 200 |
| `GET /user_search?name=admin` | 200 | 200 |
| `POST /users` (yeni e-posta) | 200 | 200 |
| `POST /users` (aynı e-posta) | 409 | 409 |
| `POST /users` (boş isim) | 422 | 422 |
| `POST /users` (geçersiz e-posta) | 422 | 422 |

## Bilerek açık bırakılan noktalar

Süre kısıtı nedeniyle çözmediğim, ama farkında olduğum konular ve olası çözümleri:

- **Tek paylaşılan SQLite bağlantısı ve `async def` içinde bloklayıcı sorgular.** Yoğun trafikte olay döngüsünü kısa süreliğine bloklar. Çözüm: istek başına bağlantı (`Depends`), `def` endpoint'leri (FastAPI bunları iş parçacığı havuzunda çalıştırır) ya da `aiosqlite`.
- **`filter_text` içindeki `%` ve `_` karakterleri `LIKE`'ta joker sayılır.** Güvenlik açığı değil (sorgu parametreli), sadece beklenmedik eşleşmelere yol açabilir. Çözüm: `ESCAPE`.
- **E-posta doğrulaması basit** (`@` kontrolü). Gerçek projede `EmailStr` (`email-validator`).
- **Tek paylaşılan API anahtarı.** Gerçek projede kullanıcı bazlı kimlik doğrulama (JWT/OAuth) ve `is_admin` alanına göre yetkilendirme.
- **Foreign key kısıtları yok** (`posts.user_id`, `comments.post_id`). SQLite'ta `PRAGMA foreign_keys=ON` ile birlikte eklenmeli. Uygulamada gönderi ve yorum oluşturan endpoint olmadığı için pratik riski düşük.
- **`/user_search` herkese açık.** İsim varlığını sorgulamaya izin verir (kullanıcı adı sızdırma). İş gereksinimine göre yetkilendirilebilir.
- **Hız sınırlama (rate limiting) ve günlükleme yok.**
- **Şema migration aracı yok** (yukarıdaki `UNIQUE` notuna bakın).


Bu projeye başlarken FastAPI ve SQLite konusunda çok bilgim yoktu. Yapay zekâ asistanından
destek aldım. İlk günlerde güvenli bir API'de nelere bakılması gerektiğini ona sorarak
öğrendim (SQL injection, kimlik doğrulama, girdi doğrulama, sayfalama gibi). Sonraki aşamada
kodu satır satır inceleyip sorunları bulmaya ve düzeltmeye odaklandım. Yapay zekâyı bir
öğrenme ve inceleme yardımcısı olarak kullandım. Her değişikliği kendim uygulayıp Swagger
üzerinden elle ve `pytest` ile çalıştırarak doğruladım.

Süreçte öğrendiğim bazı şeyler:
- Parametreli sorgu (`?`) ile f-string'le kurulan sorgu arasındaki fark ve SQL injection'ın
  pratikte nasıl çalıştığı.
- `CREATE TABLE IF NOT EXISTS` mevcut tabloyu değiştirmediği için sonradan eklediğim `UNIQUE`
  kısıtı eski veritabanında etki etmedi. Bu yüzden migration ihtiyacını gördüm.
- `async def` içindeki `time.sleep` gibi bloklayıcı çağrıların tüm servisi nasıl yavaşlattığı.
- Sunucu ve port yönetimi (eski süreçlerin portu tutması) ile testlerin gerçek veritabanından
  ayrı çalışması gerektiği.

Zamanım olsaydı ilk olarak istek başına veritabanı bağlantısı, kullanıcı bazlı kimlik
doğrulama ve bir migration aracı eklerdim. Genel olarak yaparken keyif aldığım bir görevdi,
teşekkürler.