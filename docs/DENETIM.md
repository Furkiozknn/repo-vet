# Denetim: repo-vet (30 Eylül 2026)

Yenilemeden önce `main` (0.2.0, `b77e909`) üzerinde, bu makinede (Windows 11, Python 3.12 venv ve uv'nin 3.14'ü, uv 0.12.5, Git Bash) ölçüldü. Ölçülmeyen bir şey yazılmadı. Ham çıktılar depo dışında: `kanit/repo-vet/{once,sonra}/komutlar.txt` (aynı 15 komut, iki sürüme karşı: `olc.py`; GitHub çağrıları hesabın kendi jetonuyla, jeton hiçbir yere yazılmadı).

## Temiz ortamda kurulum ve ilk sonuç

Her satır boş bir klasörde koşuldu.

| Yol | Süre | Sonuç |
|---|---|---|
| `uvx --from git+https://github.com/Furkiozknn/repo-vet repo-vet --version` (boş uv önbelleği) | 10,0 s ve 9,9 s (iki ayrı koşu; GitHub'dan çekip derliyor) | `repo-vet 0.2.0` |
| aynısı, önbellek sıcak | 3,3 s ve 2,6 s | aynı |
| `pipx install git+https://...` (`uvx pipx`, yalıtılmış `PIPX_HOME`; pipx makinede kurulu değil) | 13,6 s | `repo-vet.exe` kuruldu |
| `python -m venv` + `pip install git+https://...` | 18,8 s | `repo-vet 0.2.0` |
| `repo-vet Furkiozknn/repo-vet --skip web` (kurulu) | 3,2-3,6 s | `clean (5 checks)`, çıkış 0 |

"Tek komut, bir dakikada ilk sonuç" tutuyor: boş önbellekle kurulum + ilk denetim en kötü ölçümle ~14 s. Kurulum süresi GitHub'a ve önbelleğe bağlı.

## README komutları

| Komut | Sonuç |
|---|---|
| `uvx --from git+... repo-vet OWNER/NAME` | çalıştı (yer tutucu yerine `Furkiozknn/repo-vet`) |
| `uv tool install git+...` + `repo-vet Furkiozknn/repo-vet` | çalıştı (pipx eşdeğeri ölçüldü) |
| `repo-vet psf/requests --skip web`, `--only`, `--json`, `--markdown`, `--json-out`, `--ref` | ayrıştırıcı hepsini kabul ediyor (yeni test: README'deki her komut `argparse`'tan geçiyor); gerçek koşu `--skip web`, `--ref` (olmayan dal), yanlış jeton, ağ yok için yapıldı |
| `--from-file corpus.txt` | dosya okuma ve olmayan dosya (çıkış 2) sınandı; 29 depoluk tam koşu jeton ve zaman ister, bu görevde koşulmadı |
| README'nin ilk örneği (`prompt-template-manager` + `Furkiozknn/Furkiozknn`) | bugün de aynı çıktı: 1 bulgu (sürüm 0.1.0, hiç etiket yok), çıkış 0 |
| `PYTHONPATH=. python -m unittest discover ...` | **1 test kırmızı** (Windows'ta), aşağıda |

Sayılar: "157 tests" → koşudan 157 (uyuştu). "five to seven requests per repository" → bu görevde yeniden ölçülmedi. "29 public repositories" → `corpus.txt` 29 satır, yeniden koşulmadı.

## Hata mesajları ve `--help`

Çıkış kodları hep doğruydu (kullanım hatası 2, okunamayan depo 3). Sorun sözlerdeydi:

| Girdi | Önce | Sorun |
|---|---|---|
| `repo-vet https://github.com/Furkiozknn/repo-vet` | `not an OWNER/NAME slug: https://...` | ilk denemede en olası hata; doğru komut söylenmiyordu |
| `repo-vet .`, `repo-vet repo-vet`, `Furkiozknn/repo-vet/` | aynı tek satır | klasör tarama beklentisi, yalın ad, sondaki `/`: hiçbiri açıklanmıyordu |
| `repo-vet` (argümansız) | `nothing to check: pass OWNER/NAME or --from-file` | örnek yok, `--help`'e yönlendirme yok |
| `repo-vet Furkiozknn/yok` | `- *: skipped (no such repository, or not visible with this token)` | "skipped" tüm depo için yanlış söz; özel depo için `--token` gerektiği söylenmiyor |
| ağ yok (proxy ölü) | `- *: skipped (GitHub could not be read)` | olası nedenler yok |
| `--help` | seçenek listesi | örnek yok; çıkış kodları tek satıra sıkışmış; `--timeout` yardımsız; "klonlamaz, klasör taramaz" yazmıyor |

Önce/sonra metinleri: `kanit/repo-vet/once/`, `sonra/`.

## Hata: Windows'ta kırmızı test

`ActionStep.test_exit_code_passes_through_and_findings_are_written` Windows'ta `findings=` (boş) görüyordu: testin ürettiği bash taklidi `exec C:\Users\...\python.exe` satırında ters bölüleri kaybediyordu. Ürün hatası değil, test hatası (CI Linux'ta yeşildi); yol ileri bölülü ve tırnaklı yazıldı. Sınıf olarak: Python yolunu bash'e gömen başka test yok (grep).

## README bulguları

- İlk ekran: banner + 15 sn'lik "sesli reel" + altı rozet + `assets/demo.gif` + gerçek çıktı bloğu; kurulum komutu ekranın ortasındaydı.
- `docs/reel/reel.{gif,mp4}` ve `assets/demo.gif` ("one real run, three repositories") için **üretici depoda yok**; yeniden üretilemediği için README'den ve depodan çıkarıldı (git geçmişinde duruyorlar). Yerine `scripts/demo-uret.py` ile gerçek çıktıdan üretilen demo geldi.
- `assets/banner.svg` hesabın banner üreticisinden geliyor (GitHub mavisi, FRK-OS değil); elle değiştirilmedi (bir sonraki üretici çıktısında silinir).
- `README`'nin "Development" bölümündeki test sayısı ve `Status` tablosu 157 diyordu; 173 yapıldı.

## Testler ve CI

Önce: 157 test, Windows'ta 156 geçti + 1 kırmızı (yukarıdaki). Sonra: 173 test hepsi geçti (6,6 s). CI `TEST_TABANI` 157 → 173. CI sonuçları PR'da.

## Günlük "Ekosistem denetimi" (#19, profil deposu)

Konu 28 Eylül'den beri güncellenmemiş; gövdesinde `repo-vet`'e ait bir bulgu yok (metin araması). Kapatılacak bir şey bulunmadı. `project-meta.json` yalnızca gerçekten değişen alanlarla güncellendi (medya yolları, test sayısı); `/meta` koşturulmadı, sürüm 0.2.0 kaldı.

## Çözülmeyenler

- `--from-file corpus.txt` (29 depo) tam koşusu yapılmadı: jeton + dakikalar; README'deki "four findings across twenty-nine repositories" 22 Eylül ölçümü olarak kalıyor.
- `pipx` makinede kurulu değil; `uvx pipx` ile yalıtılmış denendi.
- Depo `description`/`homepage` ve GitHub Pages'e dokunulmadı (onay kapısı).
- Sürüm hâlâ 0.2.0 ve `main`'de etiket `v0.1.0`: yayın kararı Furki'de.
