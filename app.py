"""
app.py  –  v3
YZM714 - Sağlık YZ Etik ve Hukuki Değerlendirme Sistemi
Streamlit Arayüzü

Değişiklikler v3:
  - Kural Motoru Skoru sekmesi: 0-100 puanlı etik matris
  - Pipeline Metrikleri sekmesi: genişletilmiş (chunk sayısı, benzerlik dağılımı, kural detayları)
  - Atıfta Bulunan Kaynaklar: semantik + BM25 + hibrit skor gösterimi
  - 7. boyut (Güvenlik) arayüzde desteklendi
"""

import streamlit as st
import json
import os
from datetime import datetime
from rag_pipeline import RAGPipeline
from pdf_rapor import rapor_olustur

# ── SAYFA AYARLARI ─────────────────────────────────────────────────────────
st.set_page_config(
    page_title="YZM714 | Sağlık YZ Etik Değerlendirici",
    page_icon="🏥",
    layout="wide"
)

# ── MODERN CSS TEMASI ──────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

.ana_baslik { font-size:2.2rem; font-weight:700; color:#1E3A8A; letter-spacing:-0.03em; margin-bottom:0.2rem; }
.alt_baslik { font-size:0.95rem; color:#64748B; margin-bottom:2rem; font-weight:400; }

.sol_panel_kart { background:#F8FAFC; border: 1px solid #E2E8F0; border-radius:12px; padding:1.2rem; margin-bottom:1rem; }
.kart         { background:#FFFFFF; border-radius:10px; padding:1.2rem;
                border-left:5px solid #2563EB; box-shadow: 0 1px 3px rgba(0,0,0,0.05); margin:0.8rem 0; }
.uyari_kart   { background:#FFFBEB; border-radius:10px; padding:1rem;
                border-left:5px solid #D97706; color:#92400E; font-size:0.9rem; margin:0.6rem 0; }
.kaynak_kart  { background:#F0FDF4; border-radius:8px; padding:0.9rem;
                border: 1px solid #DCFCE7; font-size:0.88rem; color:#166534; line-height:1.5; }

.risk_yuksek  { background:#FEE2E2; color:#991B1B; padding:0.2rem 0.6rem; border-radius:6px; font-weight:600; }
.risk_orta    { background:#FEF3C7; color:#92400E; padding:0.2rem 0.6rem; border-radius:6px; font-weight:600; }
.risk_dusuk   { background:#DCFCE7; color:#166534; padding:0.2rem 0.6rem; border-radius:6px; font-weight:600; }

.puan_bar_bg  { background:#E2E8F0; border-radius:6px; height:14px; margin:2px 0 6px 0; }
.puan_bar_fg  { background:#2563EB; border-radius:6px; height:14px; }
.puan_dusuk   { background:#EF4444; }
.puan_orta    { background:#F59E0B; }
.puan_iyi     { background:#10B981; }

hr { margin: 1rem 0 !important; opacity: 0.20; }
</style>
""", unsafe_allow_html=True)


# ── PIPELINE (cache) ───────────────────────────────────────────────────────
#@st.cache_resource(show_spinner="RAG pipeline başlatılıyor (BM25 indeksi dahil)...")
def pipeline_yukle():
    return RAGPipeline()


# ── SABİT VERİLER ──────────────────────────────────────────────────────────
UC_SECENEKLERI = {
    "UC1": "Eczane Stok Yönetimi YZ (UC1)",
    "UC2": "Klinik Karar Destek / Radyoloji (UC2)",
    "UC3": "Çok Merkezli Model Eğitimi (UC3)"
}

ORNEK_SORGULAR = {
    "UC1": [
        "Eczane stok tahmin sisteminde algoritmik adalet riskleri nelerdir?",
        "KVKK kapsamında ilaç talep tahmin modeli için hangi veri işleme gereksinimleri geçerlidir?",
        "Stok YZ sisteminde hesap verebilirlik zinciri nasıl tanımlanmalıdır?"
    ],
    "UC2": [
        "Radyoloji YZ tanı sisteminin kara kutu yapısı hasta güvenliğini nasıl etkiler?",
        "AB YZ Yasası kapsamında klinik karar destek sistemi hangi uyumluluk gereksinimlerini karşılamalıdır?",
        "Malpraktis sorumluluğu açısından radyoloji YZ'sini kullanan hekimin durumu nedir?"
    ],
    "UC3": [
        "Çok merkezli hasta verileriyle model eğitiminde GDPR Madde 9 gereklilikleri nelerdir?",
        "Federated learning yöntemi Türkiye'deki sağlık veri gizliliği mevzuatıyla uyumlu mu?",
        "Çok merkezli YZ araştırmasında hasta rızasının geçerliliği nasıl değerlendirilir?"
    ]
}


def puan_rengi(puan):
    if puan >= 70: return "puan_iyi"
    if puan >= 40: return "puan_orta"
    return "puan_dusuk"


def puan_bar_html(puan, label):
    renk = puan_rengi(puan)
    return f"""
    <div style="margin-bottom:8px">
      <div style="display:flex; justify-content:space-between; font-size:0.85rem; margin-bottom:2px">
        <span><b>{label}</b></span><span><b>{puan}/100</b></span>
      </div>
      <div class="puan_bar_bg">
        <div class="puan_bar_fg {renk}" style="width:{puan}%"></div>
      </div>
    </div>
    """


# ── ANA ARAYÜZ BAŞLIK GRUBU ────────────────────────────────────────────────
st.markdown('<p class="ana_baslik">🏥 Sağlık YZ Etik ve Hukuki Değerlendirici</p>', unsafe_allow_html=True)
st.markdown('<p class="alt_baslik">YZM714 Yapay Zekânın Etik ve Hukuki Boyutu &nbsp;|&nbsp; İzmir Bakırçay Üniversitesi &nbsp;|&nbsp; 2025–2026 Bahar Dönemi &nbsp;|&nbsp; <b>Levent Turgut</b></p>', unsafe_allow_html=True)

sol, sag = st.columns([1, 2], gap="large")

# ── SOL PANEL ─────────────────────────────────────────────────────────────
with sol:
    st.caption("📋 **SİSTEM KONTROL PANELİ**")

    with st.container():
        st.markdown('<div class="sol_panel_kart">', unsafe_allow_html=True)
        st.markdown("#### 1️⃣ Senaryo ve Hızlı Sorular")
        uc_sec = st.selectbox(
            label="Değerlendirilecek Kullanım Senaryosu:",
            options=list(UC_SECENEKLERI.keys()),
            format_func=lambda x: UC_SECENEKLERI[x],
            label_visibility="visible"
        )
        st.markdown("<p style='font-size:0.85rem; color:#64748B; margin-bottom:0.4rem;'>"
                    "<b>Örnek Sorgular:</b> (Giriş alanını doldurmak için tıklayın)</p>",
                    unsafe_allow_html=True)
        btn_col1, btn_col2 = st.columns(2)
        for i, ornek in enumerate(ORNEK_SORGULAR[uc_sec]):
            target_col = btn_col1 if i % 2 == 0 else btn_col2
            with target_col:
                if st.button(f"💬 Örnek {i+1}", key=f"ornek_{uc_sec}_{i}",
                             use_container_width=True, type="secondary"):
                    st.session_state["sorgu_input"] = ornek
                    st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    with st.container():
        st.markdown('<div class="sol_panel_kart">', unsafe_allow_html=True)
        st.markdown("#### 2️⃣ Kural Motoru Konfigürasyonu")
        kural_ac = st.toggle("Etik Boyut Doğrulamasını Etkinleştir", value=True,
                             help="Kapatılırsa LLM yanıtı kural süzgecinden geçirilmez.")
        if not kural_ac:
            st.warning("⚠️ Kural motoru devre dışı. Sadece ham RAG çıktısı üretilecek.")
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("#### 🔬 Akademik Metodoloji")

    with st.expander("📚 Bilgi Tabanı Kapsamı (7 Belge)", expanded=False):
        st.markdown("""
| # | Doküman | Tür |
|---|---------|-----|
| 1 | **AB YZ Yasası** (Reg. EU 2024/1689) | Düzenleyici |
| 2 | **KVKK Rehber** (2021) | Ulusal Mevzuat |
| 3 | **WHO LMM Rehberi** (2024) | Küresel Politika |
| 4 | **ISO/IEC 42001:2023** | Standart |
| 5 | Algoritmik Adalet Literatürü | Akademik |
| 6 | Agentic YZ Sorumluluk Modelleri | Akademik |
| 7 | GDPR Madde 9 & 22 | AB Mevzuatı |
        """)

    with st.expander("⚙️ RAG Pipeline Mimarisi", expanded=False):
        st.code("""
[Kullanıcı Sorgusu]
       │
       ▼
[Semantik Retrieval]──┐
[BM25 Retrieval]──────┤ Hibrit Skor (0.6+0.4)
                      ▼
         [TOP-3 Belge Seçimi]
                      │
                      ▼
[JSON Kural Motoru] ──► Keyword + Semantic Boyut Tespiti
                      │
                      ▼
[LLM (Claude API)] ──► Bağlamsal Etik/Hukuki Analiz
                      │
                      ▼
[7 Etik Boyut Denetimi] ──► 0-100 Puanlı Skor Matrisi
                      │
                      ▼
[Yapılandırılmış Rapor + Genişletilmiş Metrikler]
        """, language="text")

    with st.expander("⚖️ 7 Etik Boyut", expanded=False):
        st.markdown("""
1. **Adalet ve Önyargı** — Bağımsızlık, Ayrışma, Yeterlilik
2. **Şeffaflık** — Kara kutu, XAI, SHAP/LIME
3. **Hesap Verebilirlik** — Sorumluluk zinciri, malpraktis
4. **Mahremiyet** — KVKK/GDPR, rıza, anonimleştirme
5. **İnsan Denetimi** — HITL, HOTL, HOOTL
6. **Hukuki Uyumluluk** — AB YZ Yasası, MDR, ISO 42001
7. **Güvenlik** — Siber güvenlik, adversarial robustness, fail-safe *(v3 yeni)*
        """)


# ── SAĞ PANEL ──────────────────────────────────────────────────────────────
with sag:
    st.markdown("### 🔍 Analiz İstemi ve Sorgu Ekranı")

    sorgu = st.text_area(
        label="Değerlendirmek istediğiniz senaryo veya hukuki/etik soruyu girin:",
        value=st.session_state.get("sorgu_input", ""),
        height=140,
        placeholder="Örn: Radyoloji teşhis asistanında kullanılan model derin öğrenme tabanlıdır. "
                    "Yanlış tanıda malpraktis sorumluluğu kime ait olur? AB YZ Yasasındaki karşılığı nedir?",
        label_visibility="visible"
    )

    btn_col1, btn_col2, btn_spacer = st.columns([1, 1, 2])
    with btn_col1:
        degerlendır = st.button("🚀 Analizi Başlat", type="primary", use_container_width=True)
    with btn_col2:
        temizle = st.button("🗑️ Alanı Temizle", use_container_width=True)

    if temizle:
        st.session_state["sorgu_input"] = ""
        st.rerun()

    st.markdown("---")

    if degerlendır and sorgu.strip():
        try:
            pipeline = pipeline_yukle()

            with st.spinner("🔄 RAG Pipeline Aktif: Hibrit Arama ──► Kural Kontrolü ──► LLM Raporu..."):
                sonuc = pipeline.calistir(sorgu.strip(), uc_sec)
                # Sorgu PDF'e geçsin — text_area boşsa session_state'ten al
                sonuc.sorgu = sorgu.strip() or st.session_state.get("sorgu_input", "")

            st.success("🎉 Etik ve Hukuki Değerlendirme Raporu Hazırlandı!")

            # ── PDF İNDİR BUTONU ──────────────────────────────────────────
            try:
                pdf_bytes = rapor_olustur(sonuc, UC_SECENEKLERI[uc_sec])
                dosya_adi = f"etik_rapor_{uc_sec}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
                st.download_button(
                    label="📥 Analizi PDF Olarak İndir",
                    data=pdf_bytes,
                    file_name=dosya_adi,
                    mime="application/pdf",
                    use_container_width=False
                )
            except Exception as pdf_err:
                st.warning(f"PDF oluşturulamadı: {pdf_err}")

            tab1, tab2, tab3, tab4 = st.tabs([
                "📊 Risk & Değerlendirme",
                "📚 Atıfta Bulunulan Kaynaklar",
                "⚖️ Kural Motoru Skoru",
                "🔬 Pipeline Metrikleri"
            ])

            # ── TAB 1: Risk & Değerlendirme ────────────────────────────────
            with tab1:
                st.subheader("📋 Yönetici Özeti ve Analiz Raporu")
                risk_str = str(sonuc.genel_risk).lower()
                if "yüksek" in risk_str or "eksik" in risk_str:
                    badge = f'<span class="risk_yuksek">🚨 {sonuc.genel_risk}</span>'
                elif "kısmen" in risk_str or "orta" in risk_str:
                    badge = f'<span class="risk_orta">⚠️ {sonuc.genel_risk}</span>'
                else:
                    badge = f'<span class="risk_dusuk">🟢 {sonuc.genel_risk}</span>'

                c1, c2 = st.columns(2)
                with c1:
                    st.markdown(f"**Senaryo:** `{UC_SECENEKLERI[uc_sec]}`")
                with c2:
                    st.markdown(f"**Risk Seviyesi:** {badge}", unsafe_allow_html=True)
                st.markdown("---")

                if sonuc.uyari_mesajlari and kural_ac:
                    for uyari in sonuc.uyari_mesajlari:
                        st.markdown(f'<div class="uyari_kart">❗ <b>Kural İhlali:</b> {uyari}</div>',
                                    unsafe_allow_html=True)

                st.markdown('<div class="kart">', unsafe_allow_html=True)
                st.markdown(sonuc.llm_yaniti)
                st.markdown('</div>', unsafe_allow_html=True)

            # ── TAB 2: Atıfta Bulunulan Kaynaklar ─────────────────────────
            with tab2:
                st.subheader("📚 Semantik Aramadan Getirilen Dokümanlar")
                st.info(f"Vektör veritabanından **{len(sonuc.getirilen_kaynaklar)}** adet referans döküman getirildi.  "
                        f"Retrieval yöntemi: **{sonuc.retrieval_yontemi}**")

                for i, k in enumerate(sonuc.getirilen_kaynaklar):
                    with st.expander(
                        f"📄 [{i+1}] {k['meta'].get('baslik','?')} — "
                        f"Hibrit: {k.get('hibrit_skor', k.get('benzerlik','?'))} | "
                        f"Sem: {k.get('sem_skor','?')} | BM25: {k.get('bm25_skor','?')}",
                        expanded=(i == 0)
                    ):
                        c1, c2 = st.columns(2)
                        with c1:
                            st.markdown(f"**Kaynak:** `{k['meta'].get('kaynak','?')}`")
                        with c2:
                            st.markdown(f"**Kategori:** `{k['meta'].get('kategori','?')}` | "
                                        f"**KAPSAM:** `{k['meta'].get('kapsam', k['meta'].get('kategori','?'))}`")
                        st.markdown("<br>", unsafe_allow_html=True)
                        st.markdown(f'<div class="kaynak_kart">{k["metin"]}</div>',
                                    unsafe_allow_html=True)

            # ── TAB 3: Kural Motoru Skoru ──────────────────────────────────
            with tab3:
                st.subheader("⚖️ Etik Matris Uyumluluğu")
                if kural_ac:
                    # Genel puan göstergesi
                    gp = sonuc.genel_puan
                    gp_renk = "#10B981" if gp >= 70 else ("#F59E0B" if gp >= 40 else "#EF4444")
                    st.markdown(
                        f"<div style='text-align:center; padding:12px; background:#F8FAFC; "
                        f"border-radius:10px; margin-bottom:16px'>"
                        f"<span style='font-size:2rem; font-weight:700; color:{gp_renk}'>{gp}</span>"
                        f"<span style='font-size:1rem; color:#64748B'>/100</span>"
                        f"<br><span style='font-size:0.85rem; color:#64748B'>Genel Etik Uyumluluk Puanı</span>"
                        f"</div>",
                        unsafe_allow_html=True
                    )

                    c1, c2 = st.columns([3, 2])
                    with c1:
                        st.markdown("**Boyut Bazlı Puan Analizi (0–100):**")
                        bars_html = ""
                        for boyut, puan in sonuc.puan_skoru.items():
                            bars_html += puan_bar_html(puan, boyut)
                        st.markdown(bars_html, unsafe_allow_html=True)

                    with c2:
                        st.markdown("**Kapsama Durumu:**")
                        for boyut, durum in sonuc.kural_skoru.items():
                            puan = sonuc.puan_skoru.get(boyut, 0)
                            if "Kapsandı" in durum:
                                st.write(f"🟢 **{boyut}:** Analiz Edildi ({puan}/100)")
                            else:
                                st.write(f"🔴 **{boyut}:** {durum}")

                        st.markdown("**Tetiklenen Kurallar:**")
                        for d in sonuc.tetiklenen_kural_detaylari:
                            yontem = d.get("tespit_yontemi", "")
                            icon = "🔀" if "+" in yontem else ("🔤" if "keyword" in yontem else "🧠")
                            st.info(f"{icon} `{d['boyut_id']}` ({yontem})")
                else:
                    st.info("Kural motoru pasif durumda.")

            # ── TAB 4: Pipeline Metrikleri ────────────────────────────────
            with tab4:
                st.subheader("🔬 Pipeline Debug — Genişletilmiş Metrikler")

                col_a, col_b = st.columns(2)
                with col_a:
                    st.markdown("**Temel Metrikler:**")
                    st.json({
                        "use_case": sonuc.use_case,
                        "retrieval_yontemi": sonuc.retrieval_yontemi,
                        "toplam_chunk_sayisi": sonuc.toplam_chunk_sayisi,
                        "getirilen_kaynak_sayisi": len(sonuc.getirilen_kaynaklar),
                        "tetiklenen_kural_sayisi": len(sonuc.tetiklenen_kurallar),
                        "genel_risk": sonuc.genel_risk,
                        "genel_puan": sonuc.genel_puan,
                        "uyari_sayisi": len(sonuc.uyari_mesajlari)
                    })

                with col_b:
                    st.markdown("**Benzerlik Skor Dağılımı:**")
                    for baslik, sem, bm25, hibrit in sonuc.benzerlik_dagilimi:
                        st.markdown(
                            f"📄 `{baslik[:35]}...`  \n"
                            f"Semantik: **{sem}** | BM25: **{bm25}** | Hibrit: **{hibrit}**"
                        )
                    st.markdown("---")
                    st.markdown("**Tetiklenen Kural Detayları:**")
                    for d in sonuc.tetiklenen_kural_detaylari:
                        kw_str  = ", ".join(d["keyword_eslesme"]) if d["keyword_eslesme"] else "—"
                        sem_str = str(d["semantic_skor"]) if d["semantic_skor"] else "—"
                        st.markdown(
                            f"⚙️ **{d['label']}**  \n"
                            f"KW eşleşme: `{kw_str}` | Semantic skor: `{sem_str}`"
                        )

        except Exception as e:
            st.error(f"Pipeline hatası: {e}")
            st.exception(e)

    elif degerlendır:
        st.warning("⚠️ Lütfen analizi başlatmadan önce bir soru veya senaryo girin.")


# ── FOOTER ─────────────────────────────────────────────────────────────────
st.markdown("<br><hr>", unsafe_allow_html=True)
st.markdown(
    "<div style='text-align:center; color:#94A3B8; font-size:0.8rem;'>"
    "YZM714 Yapay Zekânın Etik ve Hukuki Boyutu — Final Projesi Seçenek B<br>"
    "Altyapı: ChromaDB + Sentence-Transformers + BM25 + Anthropic Claude API + Streamlit<br>"
    "<b style='color:#64748B'>Levent Turgut</b> &nbsp;·&nbsp; "
    "<a href='https://github.com/trgevent' style='color:#64748B'>github.com/trgevent</a><br>"
    "İzmir Bakırçay Üniversitesi — Yapay Zekâ Mühendisliği A.B.D. © 2025–2026 Bahar Dönemi"
    "</div>",
    unsafe_allow_html=True
)
