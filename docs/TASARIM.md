# Tasarım: repo-vet ilk kullanım ve README yenilemesi (30 Eylül 2026)

## Hedef

Videodan ya da profilden gelen biri ilk dakikada şunu yapabilmeli: aracın ne yaptığını tek cümlede anlamak, tek komutla çalıştırmak, ilk sonucu almak; ilk komutu yanlış yazarsa (URL, klasör, yalın ad) doğrusunu ekranda görmek. Çekirdek davranış (altı kontrol, "bilinmeyen temiz değildir" kuralı, çıkış kodları 0/1/2/3, JSON ve Action sözleşmesi) değişmedi; sürüm numarası artmadı (0.2.0).

## Önce / sonra

| Konu | Önce | Sonra |
|---|---|---|
| README ilk ekranı | banner, 15 sn'lik sesli reel, altı rozet, kaynağı olmayan `demo.gif`, uzun gerçek-çıktı bloğu, "try it" komutu ortada | banner, tek cümlelik ad, tek cümlelik tanım, tek komutlu kurulum + ölçülmüş süre, 16 sn'lik gerçek çıktılı terminal demosu, "kullan / kullanma" tablosu, sonra rozetler ve eski gövde |
| Demo | üreticisi depoda olmayan reel + GIF | `scripts/demo-uret.py`: 4 komut gerçekten koşulur, `docs/demo/komutlar.txt` kayıttır, sayfa o kaydı yazma animasyonuyla oynatır, çıkış kodları ekranda; `demo-kayit.js` mp4/gif alır |
| Yanlış slug (URL, `.`, yalın ad, sondaki `/`) | `not an OWNER/NAME slug: X` | aynı satır + `hint:` doğru komut (URL → `repo-vet OWNER/NAME`; klasör → "API üzerinden okur, klasör taramaz") |
| Argümansız | `nothing to check...` | + örnek komut + `--help` yönlendirmesi |
| `--help` | seçenek listesi | + örnekler, çıkış kodu tablosu, "klonlamaz / klasör taramaz", `--timeout` açıklaması |
| Depo yok / ağ yok | `- *: skipped (no such repository...)` | `nothing was looked at: ...` + özel depo için `--token`; ağ için olası nedenler |
| Test | 157 (Windows'ta 1 kırmızı) | 173 hepsi yeşil (+16, `tests/test_first_run.py`: ipuçları, `--help`, okunamayan depo sözleri, README'deki her komutun ayrıştırılması; ayrıca Windows'ta kırmızı olan 1 test düzeltildi); CI tabanı 173 |

## CLI akışı

```
çalıştır             uvx --from git+https://github.com/Furkiozknn/repo-vet repo-vet OWNER/NAME
ya da kur            uv tool install git+https://github.com/Furkiozknn/repo-vet
                     (PyPI'da yok; `pip install repo-vet` README'de "çalışıyormuş gibi" yazılmadı)
denetle              repo-vet OWNER/NAME [--skip web] [--only ...]    çıkış 0/1, 2 = kullanım, 3 = okunamadı
çok depo             repo-vet --from-file corpus.txt
CI                   uses: Furkiozknn/repo-vet@main
yanlış komut         not an OWNER/NAME slug: ...  +  hint: doğru komut, çıkış 2
```

Kurulum ve ilk sonuç süresi ölçüldü (`DENETIM.md`): boş önbellekle `uvx` 9,9-10,0 s, sonra tam koşu ~3-5 s.

## Görsel dil (video sisteminden alınanlar)

Demo FRK-OS kimliğinde; `mcp-vet` yenilemesindeki sayfanın uyarlaması (aynı yazı tipi dosyaları, aynı palet).

| Ne | Nereden | Nerede |
|---|---|---|
| `zemin #0e0d0b`, panel `#14120e`, `yazi #f1ece2`, ilk vurgu `#ffc21a` | `sosyal/uret/tema.mjs` `klasik.akis` | terminal zemini, panel, metin, sarı `$` isteği/sol çizgi/`hint:`/`exit N` |
| vurgu `#ff4d6d` (mercan), `#ff7a1a` (turuncu), `#19d3e6` (camgöbeği) | `tema.mjs` klasik vurgular | `x`/hata ve "not an OWNER/NAME slug" mercan, `!` uyarı ve `not checked` turuncu, `clean` camgöbeği. Yalnızca boyama; metin değişmez |
| `doku: "izgara"` | `tema.mjs` klasik | gövdede çok soluk sabit ızgara |
| JetBrains Mono | `tema.mjs` `F.jb`; dosya `mcp-vet/assets/yazi/` (önceki yenilemede yerel önbellekten alındı) | `assets/yazi/`, SIL OFL 1.1 metniyle; indirme yok |
| `terminal: "koyu"` sahnesi, 30 ms/harf yazma | `tema.mjs` `tercih.terminal`, `sahne.js` | `scripts/demo-uret.py` sayfası |

Bilerek alınmayanlar: League Gothic başlık (README'nin görsel başlığı yok; banner profil üreticisinden), geçişler (denetim çıktısı okunmalı). Sayfa `prefers-reduced-motion`'da imleç yanıp sönmesini kapatır.

Kontrast (panel `#14120e` üstünde; mcp-vet ile aynı palet, orada WCAG göreli parlaklıktan hesaplandı): krem 15,9:1, sönük metin 8,5:1, sarı 11,6:1, mercan 5,8:1, turuncu 7,2:1, camgöbeği 10,3:1; hepsi ≥ 4,5:1.

## Kararlar ve sınırlar

- **Banner değişmedi**: hesabın banner üreticisinden geliyor (GitHub mavisi); elle değiştirmek üreticinin sonraki çıktısında silinir.
- **Reel ve eski `demo.gif` çıkarıldı**: üreticileri depoda yoktu (`DENETIM.md`). Git geçmişinde duruyorlar.
- Demo, hesabın kendi iki deposunu ve olmayan bir depoyu denetler; bulgu (`prompt-template-manager` hiç etiketlenmemiş) koşu anındaki gerçek durumdur ve `komutlar.txt` tarihlidir. GitHub çağrıları hesabın jetonuyla yapıldı (jeton yazılmadı); README "jeton gerekmez" diyor ve jetonsuz koşu da çalışıyor (60 istek/saat sınırıyla).
- `repo-vet` demoda PATH'ten gelir (`pip install .` ile kurulmuş dal sürümü); kurulum süresi ayrıca `kurulum.txt`'te `main`'den ölçülür.
- Demo dikey 1080x1920 kaydı depoya girmedi; günlük video hattı için `sosyal/medya/projeler/repo-vet/terminal.mp4` (16,4 s, H.264 yuv420p, sessiz).
- Sürüm, etiket, PyPI, dizin/awesome-list başvurusu, Pages ve GitHub description/homepage **değişmedi** (onay kapısı).
