"""
pdf_rapor.py  –  v4
YZM714 - Sağlık YZ Etik Değerlendirme Sistemi — PDF Rapor Üretici
Yeni tasarım: başlık bandı, bilgi kartı, risk/puan banner, renkli bölüm başlıkları
"""

from fpdf import FPDF
from datetime import datetime
import os

PAGE_W = 174  # A4: 210 - 18 - 18
NAVY   = (30, 58, 138)
GREEN  = (16, 185, 129)
GREEN_BG = (209, 250, 229)
GREEN_FG = (6, 95, 70)
AMBER_BG = (254, 243, 199)
AMBER_FG = (146, 64, 14)
RED_BG   = (254, 226, 226)
RED_FG   = (153, 27, 27)
BLUE_BG  = (240, 245, 255)
BLUE_BD  = (199, 217, 245)
LGRAY    = (248, 250, 252)
GRAY     = (85, 85, 85)
WHITE    = (255, 255, 255)


def temizle(s):
    if not isinstance(s, str):
        s = str(s)
    replacements = {
        "✅":"[OK]","⚠️":"[!]","🟢":"","🟡":"","🔴":"","❗":"!",
        "🚨":"(!)","⚙️":"*","📄":"-","#":"","→":"->","✓":"v","✗":"x",
        "\u2705":"[OK]","\U0001f7e2":"","\U0001f534":"",
        "Kapsamlı":"KAPSAMLI","Kısmen":"KISMEN",
        "[OK] Kapsamlı":"KAPSAMLI","[OK] Kapsandı":"Kapsandı",
        "[OK]":"",
        "—":"-","–":"-","…":"...","'":"'","'":"'",""":'"',""":'"',
        "\u2014":"-","\u2013":"-","\u2026":"...",
        "\u2018":"'","\u2019":"'","\u201c":'"',"\u201d":'"',
    }
    for k, v in replacements.items():
        s = s.replace(k, v)
    # Kalan non-ASCII karakterleri koru (Türkçe), sorunluları temizle
    result = []
    for ch in s:
        cp = ord(ch)
        if cp < 128 or (160 <= cp <= 591) or (608 <= cp <= 687):
            result.append(ch)
        else:
            result.append("?")
    return "".join(result).strip()


class EtikRaporPDF(FPDF):
    def __init__(self):
        super().__init__()
        base     = os.path.dirname(os.path.abspath(__file__))
        font_dir = os.path.join(base, "fonts")
        self.add_font("DV",  "",  os.path.join(font_dir, "DejaVuSans.ttf"))
        self.add_font("DV",  "B", os.path.join(font_dir, "DejaVuSans-Bold.ttf"))
        self.add_font("DV",  "I", os.path.join(font_dir, "DejaVuSans-Oblique.ttf"))
        self.set_margins(18, 24, 18)
        self.set_auto_page_break(auto=True, margin=20)

    def header(self):
        # Lacivert üst bant
        self.set_fill_color(*NAVY)
        self.rect(0, 0, 210, 10, "F")
        self.set_y(1.5)
        self.set_font("DV", "B", 8)
        self.set_text_color(*WHITE)
        self.cell(PAGE_W * 0.6, 7, "YZM714 – Sağlık YZ Etik ve Hukuki Değerlendirici", align="L")
        self.set_font("DV", "I", 7)
        self.set_text_color(179, 198, 231)
        self.cell(PAGE_W * 0.4, 7,
                  f"İzmir Bakırçay Üniversitesi  |  {datetime.now().strftime('%d.%m.%Y %H:%M')}",
                  align="R", new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(*GRAY)
        self.ln(4)

    def footer(self):
        self.set_y(-13)
        self.set_draw_color(200, 200, 200)
        self.set_line_width(0.3)
        self.line(18, self.get_y(), 18 + PAGE_W, self.get_y())
        self.ln(1)
        self.set_font("DV", "I", 7)
        self.set_text_color(160, 160, 160)
        self.cell(0, 4, f"YZM714 Final Projesi Seçenek B  |  Sayfa {self.page_no()}", align="C")

    def kapak_baslik(self, baslik, alt):
        self.set_font("DV", "B", 17)
        self.set_text_color(*NAVY)
        self.cell(PAGE_W, 9, baslik, align="C", new_x="LMARGIN", new_y="NEXT")
        self.set_font("DV", "I", 9)
        self.set_text_color(100, 100, 100)
        self.cell(PAGE_W, 5, alt, align="C", new_x="LMARGIN", new_y="NEXT")
        # Çift çizgi
        self.set_draw_color(*NAVY)
        self.set_line_width(0.8)
        self.line(18, self.get_y()+2, 18+PAGE_W, self.get_y()+2)
        self.set_line_width(0.3)
        self.line(18, self.get_y()+4, 18+PAGE_W, self.get_y()+4)
        self.ln(8)

    def bilgi_kart(self, items):
        """Bilgi satırlarını düz metin olarak yazar — kutu/tablo yok, taşma yok."""
        for etiket, deger in items:
            deger_str = temizle(str(deger))
            # Etiket satırı
            self.set_font("DV", "B", 8)
            self.set_text_color(*NAVY)
            self.cell(0, 5, temizle(str(etiket)) + ":", new_x="LMARGIN", new_y="NEXT")
            # Değer satırı — tam sayfa genişliği, wrap destekli
            self.set_font("DV", "", 8)
            self.set_text_color(*GRAY)
            self.set_x(22)  # hafif girinti
            self.multi_cell(PAGE_W - 4, 5, deger_str)
            self.ln(1)
        self.ln(3)

    def risk_puan_banner(self, risk_str, genel_puan):
        risk = temizle(str(risk_str)).upper()
        risk_lower = risk.lower()
        if "kapsaml" in risk_lower:
            bg, fg = GREEN_BG, GREEN_FG
        elif "kismen" in risk_lower:
            bg, fg = AMBER_BG, AMBER_FG
        else:
            bg, fg = RED_BG, RED_FG

        if genel_puan >= 70: p_bg, p_fg = GREEN_BG, GREEN_FG
        elif genel_puan >= 40: p_bg, p_fg = AMBER_BG, AMBER_FG
        else: p_bg, p_fg = RED_BG, RED_FG

        half = (PAGE_W - 6) // 2
        y = self.get_y()

        # Risk kutusu
        self.set_fill_color(*bg)
        self.set_draw_color(*fg)
        self.set_line_width(0.5)
        self.rect(18, y, half, 14, "FD")
        self.set_font("DV", "B", 7)
        self.set_text_color(*fg)
        self.set_xy(18, y+2)
        self.cell(half, 5, "GENEL RİSK", align="C", new_x="LMARGIN", new_y="NEXT")
        self.set_font("DV", "B", 12)
        self.set_xy(18, y+7)
        self.cell(half, 6, risk, align="C")

        # Puan kutusu
        self.set_fill_color(*p_bg)
        self.set_draw_color(*p_fg)
        self.rect(18+half+6, y, half, 14, "FD")
        self.set_font("DV", "B", 7)
        self.set_text_color(*p_fg)
        self.set_xy(18+half+6, y+2)
        self.cell(half, 5, "ETİK PUAN", align="C", new_x="LMARGIN", new_y="NEXT")
        self.set_font("DV", "B", 12)
        self.set_xy(18+half+6, y+7)
        self.cell(half, 6, f"{genel_puan} / 100", align="C")

        self.set_xy(18, y+14)
        self.set_text_color(*GRAY)
        self.ln(6)

    def bolum_baslik(self, no, text):
        self.ln(3)
        self.set_fill_color(*NAVY)
        self.set_text_color(*WHITE)
        self.set_font("DV", "B", 10)
        self.cell(PAGE_W, 8, f"  {no}   {temizle(text)}", fill=True,
                  new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(*GRAY)
        self.ln(2)

    def alt_baslik(self, text):
        self.set_font("DV", "B", 9)
        self.set_text_color(*NAVY)
        self.cell(PAGE_W, 6, temizle(text), new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(*NAVY)
        self.set_line_width(0.3)
        self.line(18, self.get_y(), 18+PAGE_W, self.get_y())
        self.set_text_color(*GRAY)
        self.ln(2)

    def txt(self, text, size=8.5, bold=False, italic=False, color=None, indent=0):
        style = ("B" if bold else "") + ("I" if italic else "")
        self.set_font("DV", style, size)
        self.set_text_color(*(color or GRAY))
        if indent:
            self.set_x(18+indent)
        self.multi_cell(PAGE_W-indent, 5, temizle(str(text)))
        self.ln(0.5)

    def kanun_kutu(self, text):
        self.set_fill_color(*BLUE_BG)
        self.set_draw_color(*BLUE_BD)
        self.set_line_width(0.4)
        self.set_font("DV", "I", 7.5)
        self.set_text_color(30, 70, 160)
        self.multi_cell(PAGE_W, 4.5, f"  {temizle(text)}", fill=True, border=1)
        self.set_text_color(*GRAY)
        self.ln(3)

    def puan_bar(self, etiket, puan, bar_w=90):
        self.set_font("DV", "", 8)
        self.set_text_color(*GRAY)
        self.cell(62, 6, temizle(str(etiket)))
        # arka plan
        self.set_fill_color(226, 232, 240)
        self.rect(self.get_x(), self.get_y()+2, bar_w, 3, "F")
        # ön plan
        if puan >= 70:   self.set_fill_color(*GREEN)
        elif puan >= 40: self.set_fill_color(245, 158, 11)
        else:            self.set_fill_color(239, 68, 68)
        dolu = int(bar_w * puan / 100)
        if dolu > 0:
            self.rect(self.get_x(), self.get_y()+2, dolu, 3, "F")
        self.set_x(self.get_x() + bar_w + 4)
        self.set_font("DV", "B", 8)
        if puan >= 70:   self.set_text_color(*GREEN_FG)
        elif puan >= 40: self.set_text_color(*AMBER_FG)
        else:            self.set_text_color(*RED_FG)
        self.cell(0, 6, f"{puan}/100", new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(*GRAY)

    def tablo(self, kolonlar, genislikler, satirlar):
        self.set_font("DV", "B", 8)
        self.set_fill_color(*NAVY)
        self.set_text_color(*WHITE)
        for k, g in zip(kolonlar, genislikler):
            self.cell(g, 6, temizle(str(k)), border=1, fill=True)
        self.ln()
        self.set_text_color(*GRAY)
        for ri, satir in enumerate(satirlar):
            if ri % 2 == 0: self.set_fill_color(*LGRAY)
            else:            self.set_fill_color(*WHITE)
            self.set_font("DV", "", 7.5)
            x0, y0 = self.get_x(), self.get_y()
            max_y = y0
            for i, (val, g) in enumerate(zip(satir, genislikler)):
                self.set_xy(x0 + sum(genislikler[:i]), y0)
                self.multi_cell(g, 5, temizle(str(val)), border=1, fill=True)
                if self.get_y() > max_y: max_y = self.get_y()
            self.set_xy(x0, max_y)
        self.ln(3)


T_BDP = [94, 50, 30]
T_PD  = [100, 74]
T_BEN = [84, 30, 30, 30]
T_KRL = [52, 36, 60, 26]


def rapor_olustur(sonuc, uc_baslik: str) -> bytes:
    pdf = EtikRaporPDF()
    pdf.add_page()

    # ── BAŞLIK ──
    pdf.kapak_baslik(
        "ETİK VE HUKUKİ DEĞERLENDİRME RAPORU",
        "YZM714 – Final Projesi Seçenek B  |  İzmir Bakırçay Üniversitesi"
    )

    # ── BİLGİ KARTI ──
    sorgu_k = str(sonuc.sorgu).strip()
    if not sorgu_k:
        sorgu_k = "(Örnek sorgu butonu kullanıldı)"
    pdf.bilgi_kart([
        ("Senaryo",      uc_baslik),
        ("Sorgu",        sorgu_k[:220] + ("..." if len(sorgu_k) > 220 else "")),
        ("Tarih",        datetime.now().strftime("%d.%m.%Y %H:%M")),
        ("Retrieval",    str(getattr(sonuc, "retrieval_yontemi", "Semantik + BM25 Hibrit"))),
        ("Toplam Chunk", str(getattr(sonuc, "toplam_chunk_sayisi", "—"))),
    ])

    # ── RİSK / PUAN BANNER ──
    pdf.risk_puan_banner(sonuc.genel_risk, getattr(sonuc, "genel_puan", 0))

    # ── BÖLÜM 1: LLM ANALİZİ ──
    pdf.bolum_baslik("1", "Etik ve Hukuki Değerlendirme")
    llm = str(sonuc.llm_yaniti)
    for ch in ["**", "__"]:
        llm = llm.replace(ch, "")
    # Satırları işle: başlıklar ve normal metin
    for satir in llm.split("\n"):
        s = satir.strip()
        if not s:
            pdf.ln(1)
            continue
        # Yatay çizgi işaretlerini atla — tüm varyasyonlar
        if s.replace("-","").replace("–","").replace("=","").replace("*","").strip() == "":
            continue
        # Başlık tespiti
        if any(s.upper().startswith(x) for x in ["BOYUT","ÖNERI","ÖNERI","BÖLÜM","TÜRKİYE","ETİK","3 KR","BÖLÜM"]):
            pdf.alt_baslik(s)
        elif s.startswith(("İlgili","> İlgili","> Bu öneri","Bu öneri","> Neden","Neden Kritik")):
            pdf.kanun_kutu(s.lstrip("> "))
        elif s.startswith(("- ","* ","• ","+ ")):
            # Bullet normalize et
            pdf.txt("- " + s[2:].strip(), indent=5)
        elif s.startswith(("1.","2.","3.","4.","5.","6.","7.","8.","9.")):
            pdf.txt(s, bold=True)
        else:
            pdf.txt(s)

    # ── BÖLÜM 2: ETİK SKOR ──
    pdf.add_page()
    pdf.bolum_baslik("2", "Etik Matris — Boyut Bazlı Puan Analizi (0–100)")

    puan_skor  = getattr(sonuc, "puan_skoru",  {}) or {}
    kural_skor = getattr(sonuc, "kural_skoru", {}) or {}

    if puan_skor:
        pdf.ln(2)
        for boyut, puan in puan_skor.items():
            pdf.puan_bar(str(boyut), int(puan) if isinstance(puan,(int,float)) else 0)
        pdf.ln(4)

    if kural_skor:
        pdf.alt_baslik("Kapsama Durumu")
        satirlar = []
        for boyut, durum in kural_skor.items():
            puan = puan_skor.get(boyut, "—")
            puan_s = f"{puan}/100" if isinstance(puan,int) else str(puan)
            satirlar.append([str(boyut), str(durum), puan_s])
        pdf.tablo(["Boyut","Durum","Puan"], T_BDP, satirlar)
    else:
        pdf.txt("Kural motoru pasif durumda — etik boyut analizi yapılmadı.",
                size=9, italic=True, color=AMBER_FG)

    if sonuc.uyari_mesajlari:
        pdf.alt_baslik("Kural İhlalleri")
        for uyari in sonuc.uyari_mesajlari:
            pdf.set_fill_color(*AMBER_BG)
            pdf.set_font("DV","",8)
            pdf.multi_cell(PAGE_W, 5, f"  [!]  {temizle(uyari)}", fill=True, border=1)
            pdf.ln(1)

    # ── BÖLÜM 3: KAYNAKLAR ──
    pdf.add_page()
    pdf.bolum_baslik("3", "Atıfta Bulunulan Kaynaklar")
    pdf.txt(f"Vektör veritabanından {len(sonuc.getirilen_kaynaklar)} adet referans döküman getirildi.", size=9)
    pdf.ln(2)

    for i, k in enumerate(sonuc.getirilen_kaynaklar):
        baslik_k = str(k["meta"].get("baslik","?"))[:55]
        kaynak   = str(k["meta"].get("kaynak","?"))[:85]
        kategori = str(k["meta"].get("kategori","?"))
        sem      = k.get("sem_skor",  k.get("benzerlik","—"))
        bm25     = k.get("bm25_skor", "—")
        hibrit   = k.get("hibrit_skor",k.get("benzerlik","—"))

        pdf.set_fill_color(*BLUE_BG)
        pdf.set_font("DV","B",9)
        pdf.set_text_color(*NAVY)
        pdf.set_x(18)
        pdf.cell(PAGE_W, 6, f"[{i+1}]  {temizle(baslik_k)}", fill=True,
                 new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(100,100,100)
        pdf.set_font("DV","",7.5)
        pdf.set_x(18)
        pdf.multi_cell(PAGE_W, 4, f"Kaynak: {temizle(kaynak)}   |   Kategori: {temizle(kategori)}")
        def fmt(v):
            try: return f"{float(v):.3f}"
            except: return str(v)
        pdf.set_x(18)
        pdf.multi_cell(PAGE_W, 4,
                 f"Semantik: {fmt(sem)}   |   BM25: {fmt(bm25)}   |   Hibrit: {fmt(hibrit)}")
        pdf.ln(1)
        pdf.set_text_color(*GRAY)
        pdf.set_fill_color(240,253,244)
        pdf.set_font("DV","",7.5)
        # Ham metadata satırlarını filtrele, son tam cümlede kes
        metin_raw = str(k["metin"])
        metin_satirlar = []
        for satir in metin_raw.split("\n"):
            s = satir.strip()
            if not s:
                continue
            if any(s.upper().startswith(p) for p in ["BELGE ", "KAYNAK:", "KATEGORI:", "KATEGOR\u0130:", "KAPSAM:"]):
                continue
            metin_satirlar.append(s)
        metin_temiz = " ".join(metin_satirlar)
        LIMIT = 800
        if len(metin_temiz) > LIMIT:
            kisim = metin_temiz[:LIMIT]
            son_nokta = max(kisim.rfind(". "), kisim.rfind("! "), kisim.rfind("? "))
            metin_k = kisim[:son_nokta+1] if son_nokta > 200 else kisim + "..."
        else:
            metin_k = metin_temiz
        pdf.set_x(18)
        pdf.multi_cell(PAGE_W, 4, temizle(metin_k), fill=True, border=1)
        pdf.ln(4)

    # ── BÖLÜM 4: PIPELINE ──
    pdf.add_page()
    pdf.bolum_baslik("4", "Pipeline Metrikleri")

    pdf.tablo(["Parametre","Değer"], T_PD, [
        ["Use Case",         str(sonuc.use_case)],
        ["Retrieval Yöntemi",str(getattr(sonuc,"retrieval_yontemi","—"))],
        ["Toplam Chunk",     str(getattr(sonuc,"toplam_chunk_sayisi","—"))],
        ["Getirilen Kaynak", str(len(sonuc.getirilen_kaynaklar))],
        ["Tetiklenen Kural", str(len(sonuc.tetiklenen_kurallar))],
        ["Genel Risk",       temizle(str(sonuc.genel_risk))],
        ["Genel Puan",       f"{getattr(sonuc,'genel_puan','—')}/100"],
        ["Uyarı Sayısı",     str(len(sonuc.uyari_mesajlari))],
    ])

    benzerlik = getattr(sonuc,"benzerlik_dagilimi",[])
    if benzerlik:
        pdf.alt_baslik("Benzerlik Skor Dağılımı")
        satirlar_b = []
        for item in benzerlik:
            if len(item)==4: bsh,sem2,bm2,hib = item
            else: bsh,sem2,bm2,hib = item[0],item[1],"—",item[-1]
            def f(v):
                try: return f"{float(v):.3f}"
                except: return str(v)
            satirlar_b.append([str(bsh)[:38], f(sem2), f(bm2), f(hib)])
        pdf.tablo(["Kaynak","Semantik","BM25","Hibrit"], T_BEN, satirlar_b)

    detaylar = getattr(sonuc,"tetiklenen_kural_detaylari",[])
    if detaylar:
        pdf.alt_baslik("Tetiklenen Kural Detayları")
        satirlar_k = []
        for d in detaylar:
            kw_str = ", ".join(d.get("keyword_eslesme",[]))[:25] or "—"
            satirlar_k.append([
                str(d.get("label",d.get("boyut_id","?")))[:22],
                str(d.get("tespit_yontemi","?"))[:15],
                kw_str, str(d.get("semantic_skor","—"))
            ])
        pdf.tablo(["Boyut","Yöntem","KW Eşleşme","Sem. Skor"], T_KRL, satirlar_k)

    pdf.set_font("DV","I",7)
    pdf.set_text_color(160,160,160)
    pdf.multi_cell(PAGE_W, 4,
        "Bu rapor YZM714 – Yapay Zekânın Etik ve Hukuki Boyutu dersi Final Projesi Seçenek B "
        "kapsamında otomatik olarak üretilmiştir. İzmir Bakırçay Üniversitesi © 2025–2026 Bahar Dönemi")

    return bytes(pdf.output())
