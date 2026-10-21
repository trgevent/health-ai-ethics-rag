"""
rag_pipeline.py  –  v3.1
Pipeline: Sorgu → Hibrit Retrieval (Semantik + BM25) → Kural Filtreleme → LLM → Kural Doğrulama → Çıktı

Düzeltmeler v3.1:
  - Semantik skor "0" hatası giderildi (ChromaDB ID eşleşme sorunu)
  - Puan hesaplama kalibrasyonu düzeltildi (100/100 sorunu)
  - BM25 indeksi ChromaDB ile aynı sırada tutuluyor

LLM_BACKEND:
  "anthropic" → Claude API (varsayılan)
  "ollama"    → Yerel Ollama
  "openai"    → OpenAI API
"""

import os, json, requests
import chromadb
from sentence_transformers import SentenceTransformer, util
from dataclasses import dataclass, field
from rank_bm25 import BM25Okapi

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
CHROMA_DIR  = os.path.join(BASE_DIR, "chroma_db")
RULES_PATH  = os.path.join(BASE_DIR, "rules", "ethics_rules.json")
COLLECTION  = "saglik_yz_etik"
EMBED_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
TOP_K       = 3
MAX_TOKENS  = 8000

SEMANTIC_WEIGHT  = 0.6
BM25_WEIGHT      = 0.4
SEMANTIC_THRESHOLD = 0.35

LLM_BACKEND  = os.getenv("LLM_BACKEND", "anthropic")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")
OLLAMA_URL   = os.getenv("OLLAMA_URL",   "http://localhost:11434/api/generate")


@dataclass
class RAGSonucu:
    sorgu: str
    use_case: str
    tetiklenen_kurallar: list
    getirilen_kaynaklar: list
    llm_yaniti: str
    kural_skoru: dict
    puan_skoru: dict
    genel_risk: str
    genel_puan: int
    uyari_mesajlari: list = field(default_factory=list)
    toplam_chunk_sayisi: int = 0
    benzerlik_dagilimi: list = field(default_factory=list)
    tetiklenen_kural_detaylari: list = field(default_factory=list)
    retrieval_yontemi: str = "Semantik + BM25 Hibrit"


# ── KURAL MOTORU ──────────────────────────────────────────────────────────
class KuralMotoru:
    def __init__(self, rules_path, embed_model):
        with open(rules_path, "r", encoding="utf-8") as f:
            self.rules = json.load(f)
        self.boyutlar    = {b["id"]: b for b in self.rules["dimensions"]}
        self.uc_profiler = self.rules["use_case_profilleri"]
        self.embed_model = embed_model

    def keyword_tarama(self, metin):
        metin_lower = metin.lower()
        eslesmeler = {}
        for bid, b in self.boyutlar.items():
            eslesen = [kw for kw in b["keywords"] if kw.lower() in metin_lower]
            if eslesen:
                eslesmeler[bid] = eslesen
        return eslesmeler

    def semantic_tarama(self, metin):
        metin_emb = self.embed_model.encode(metin, convert_to_tensor=True)
        bulunanlar = {}
        for bid, b in self.boyutlar.items():
            kavramlar = b.get("embedding_concepts", [])
            if not kavramlar:
                continue
            kavram_emb = self.embed_model.encode(kavramlar, convert_to_tensor=True)
            benzerlikler = util.cos_sim(metin_emb, kavram_emb)[0]
            max_skor = float(benzerlikler.max())
            if max_skor >= SEMANTIC_THRESHOLD:
                bulunanlar[bid] = round(max_skor, 3)
        return bulunanlar

    def hibrit_boyut_tespiti(self, metin):
        kw_eslesmeler  = self.keyword_tarama(metin)
        sem_eslesmeler = self.semantic_tarama(metin)
        tum_boyutlar   = set(kw_eslesmeler.keys()) | set(sem_eslesmeler.keys())
        detaylar = []
        for bid in tum_boyutlar:
            kw  = kw_eslesmeler.get(bid, [])
            sem = sem_eslesmeler.get(bid, 0.0)
            detaylar.append({
                "boyut_id": bid,
                "label": self.boyutlar[bid]["label"],
                "keyword_eslesme": kw,
                "semantic_skor": sem,
                "tespit_yontemi": "keyword+semantic" if (kw and sem) else ("keyword" if kw else "semantic")
            })
        return list(tum_boyutlar), detaylar

    def uc_kritik_boyutlari(self, uc_id):
        return self.uc_profiler.get(uc_id, {}).get("kritik_boyutlar", list(self.boyutlar))

    def sistem_prompt_uret(self, uc_id, tetiklenenler):
        uc = self.uc_profiler.get(uc_id, {})
        boyutlar_str = ", ".join(
            self.boyutlar[b]["label"]
            for b in tetiklenenler if b in self.boyutlar
        )
        return (
            f"Saglik YZ etik degerlendirme asistanisin. Turkce yaz.\n"
            f"Senaryo: {uc.get('baslik', uc_id)} | Risk: {uc.get('risk_seviyesi','?')}\n"
            f"AB YZ Yasasi: {uc.get('ab_yz_yasasi_kategori','?')}\n"
            f"Boyutlar: {boyutlar_str}\n"
            f"Her boyut icin SADECE: 1 paragraf risk analizi + ilgili yasa maddesi.\n"
            f"Turkiye boslukları: maksimum 3 madde.\n"
            f"3 kritik oneri: her biri baslik + 3 madde + 2 cumle neden kritik.\n"
            f"KISALT. Toplam 1500 kelimeyi gecme.\n"
            f"ZORUNLU: 3 oneri tam bitmeden durma.\n"
        )

    def puan_hesapla(self, llm_yaniti, boyut_id):
        """0-100 puan — gerçekçi kalibrasyon."""
        b = self.boyutlar.get(boyut_id, {})
        yanit_lower = llm_yaniti.lower()
        label_lower = b.get("label", "").lower()
        keywords    = b.get("keywords", [])
        kontrol_sq  = b.get("kontrol_soruları", [])

        # Temel varlık: label veya keyword var mı?
        kw_eslesme = [kw for kw in keywords if kw.lower() in yanit_lower]
        label_var  = label_lower in yanit_lower or len(kw_eslesme) > 0
        if not label_var:
            return 0

        # Derinlik: kaç farklı keyword eşleşti (max 40 puan)
        kw_puan = min(len(kw_eslesme) * 8, 40)

        # Kontrol soruları: keyword overlap (max 35 puan)
        sq_puan = 0
        for sq in kontrol_sq:
            sq_words = [w for w in sq.lower().split() if len(w) > 4]
            if any(w in yanit_lower for w in sq_words):
                sq_puan += int(35 / max(len(kontrol_sq), 1))

        # Yasa maddesi atfı (max 20 puan)
        maddeler = b.get("ilgili_maddeler", [])
        madde_puan = 0
        for m in maddeler:
            parcalar = [p for p in m.split() if len(p) > 3]
            if any(p.lower() in yanit_lower for p in parcalar):
                madde_puan += int(20 / max(len(maddeler), 1))
        madde_puan = min(madde_puan, 20)

        # Temel baz puan (5 puan — var olması yeterli)
        toplam = 5 + kw_puan + sq_puan + madde_puan
        return min(toplam, 95)  # max 95, mükemmel sistem yoktur

    def kural_dogrulama(self, llm_yaniti, uc_id, tetiklenen_boyutlar=None):
        uc_kritik = self.uc_kritik_boyutlari(uc_id)
        # Tetiklenen boyutları da ekle — Etik Matris'te tümü görünsün
        ekstra = [b for b in (tetiklenen_boyutlar or []) if b not in uc_kritik]
        tum_boyutlar = uc_kritik + ekstra
        skor, puan_skor, uyarilar = {}, {}, []
        yanit_lower = llm_yaniti.lower()

        for bid in tum_boyutlar:
            b     = self.boyutlar.get(bid, {})
            label = b.get("label", bid)
            puan  = self.puan_hesapla(llm_yaniti, bid)
            puan_skor[label] = puan

            bulundu = label.lower() in yanit_lower or \
                      any(kw.lower() in yanit_lower for kw in b.get("keywords", []))
            skor[label] = "Kapsandı" if bulundu else "Eksik"
            if not bulundu:
                uyarilar.append(f"'{label}' boyutu yanıtta yeterince ele alınmadı.")

        eksik    = sum(1 for s in skor.values() if "Eksik" in s)
        genel    = "Kapsamlı" if eksik == 0 else ("Kısmen" if eksik <= 1 else "Eksik Boyutlar")

        # Ağırlıklı genel puan (sadece uc_kritik boyutlar üzerinden)
        toplam_agirlik   = sum(self.boyutlar[bid].get("agirlik", 15) for bid in uc_kritik if bid in self.boyutlar)
        agirlikli_toplam = sum(
            puan_skor.get(self.boyutlar[bid]["label"], 0) * self.boyutlar[bid].get("agirlik", 15)
            for bid in uc_kritik if bid in self.boyutlar
        )
        genel_puan = int(agirlikli_toplam / max(toplam_agirlik, 1))

        return skor, puan_skor, genel_puan, genel, uyarilar


# ── LLM ÇAĞRILARI ─────────────────────────────────────────────────────────
def llm_anthropic(sistem_prompt, kullanici_mesaji):
    import anthropic
    client = anthropic.Anthropic()
    r = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=MAX_TOKENS,
        system=sistem_prompt,
        messages=[{"role": "user", "content": kullanici_mesaji}]
    )
    return r.content[0].text

def llm_ollama(sistem_prompt, kullanici_mesaji):
    tam_prompt = f"{sistem_prompt}\n\n{kullanici_mesaji}"
    r = requests.post(OLLAMA_URL, json={
        "model": OLLAMA_MODEL, "prompt": tam_prompt,
        "stream": False, "options": {"num_predict": MAX_TOKENS}
    }, timeout=180)
    r.raise_for_status()
    return r.json().get("response", "")

def llm_openai(sistem_prompt, kullanici_mesaji):
    import openai
    client = openai.OpenAI()
    r = client.chat.completions.create(
        model="gpt-4o-mini", max_tokens=MAX_TOKENS,
        messages=[{"role": "system", "content": sistem_prompt},
                  {"role": "user",   "content": kullanici_mesaji}]
    )
    return r.choices[0].message.content

def llm_cagir(sistem_prompt, kullanici_mesaji):
    if LLM_BACKEND == "anthropic": return llm_anthropic(sistem_prompt, kullanici_mesaji)
    elif LLM_BACKEND == "ollama":  return llm_ollama(sistem_prompt, kullanici_mesaji)
    elif LLM_BACKEND == "openai":  return llm_openai(sistem_prompt, kullanici_mesaji)
    else: raise ValueError(f"Bilinmeyen LLM_BACKEND: {LLM_BACKEND}")


# ── RAG PIPELINE ──────────────────────────────────────────────────────────
class RAGPipeline:
    def __init__(self):
        print(f"RAG Pipeline başlatılıyor... (Backend: {LLM_BACKEND})")
        self.embed_model = SentenceTransformer(EMBED_MODEL)
        client           = chromadb.PersistentClient(path=CHROMA_DIR)
        self.collection  = client.get_collection(COLLECTION)
        self.kural_motoru = KuralMotoru(RULES_PATH, self.embed_model)

        # BM25: ChromaDB ile AYNI sırada tut
        print("  → BM25 indeksi oluşturuluyor...")
        tum = self.collection.get(include=["documents", "metadatas", "embeddings"])
        self.chroma_ids   = tum["ids"]           # ["chunk_0", "chunk_1", ...]
        self.tum_docs     = tum["documents"]
        self.tum_metas    = tum["metadatas"]
        self.toplam_chunk = len(self.tum_docs)
        # ID → index map (birleştirme için)
        self.id_to_idx    = {cid: i for i, cid in enumerate(self.chroma_ids)}
        tokenized         = [doc.lower().split() for doc in self.tum_docs]
        self.bm25         = BM25Okapi(tokenized)
        print(f"  → BM25 hazır. Toplam chunk: {self.toplam_chunk}")
        print("✅ Pipeline hazır.")

    def retrieve(self, sorgu, uc_id=None):
        """Hibrit retrieval: Semantik + BM25, aynı ID uzayında birleştirme."""
        uc = self.kural_motoru.uc_profiler.get(uc_id or "", {})
        sorgu_zengin = f"{uc.get('baslik','')} {sorgu}".strip()

        # -- Semantik --
        emb = self.embed_model.encode([sorgu_zengin])[0].tolist()
        res = self.collection.query(
            query_embeddings=[emb],
            n_results=min(TOP_K * 2, self.toplam_chunk),
            include=["documents", "metadatas", "distances"]
        )
        sem_scores = {}
        for i, cid in enumerate(res["ids"][0]):
            sem_scores[cid] = round(1 - res["distances"][0][i], 3)

        # -- BM25 --
        tokenized_sorgu = sorgu.lower().split()
        bm25_raw = self.bm25.get_scores(tokenized_sorgu)
        max_bm25 = max(bm25_raw) if max(bm25_raw) > 0 else 1.0
        bm25_scores = {}
        for idx, score in enumerate(bm25_raw):
            if score > 0:
                cid = self.chroma_ids[idx]
                bm25_scores[cid] = round(score / max_bm25, 3)

        # -- Birleştir (aynı ID uzayı garantili) --
        tum_ids = set(sem_scores.keys()) | set(bm25_scores.keys())
        birlestir = {}
        for cid in tum_ids:
            sem  = sem_scores.get(cid, 0.0)
            bm25 = bm25_scores.get(cid, 0.0)
            hibrit = round(SEMANTIC_WEIGHT * sem + BM25_WEIGHT * bm25, 3)
            idx  = self.id_to_idx.get(cid, -1)
            if idx < 0:
                continue
            birlestir[cid] = {
                "metin":       self.tum_docs[idx],
                "meta":        self.tum_metas[idx],
                "sem_skor":    sem,
                "bm25_skor":   bm25,
                "hibrit_skor": hibrit,
                "benzerlik":   hibrit
            }

        sirali = sorted(birlestir.values(), key=lambda x: x["hibrit_skor"], reverse=True)
        return sirali[:TOP_K]

    def calistir(self, sorgu, uc_id="UC1"):
        kaynaklar = self.retrieve(sorgu, uc_id)

        tum_boyutlar, kural_detaylari = self.kural_motoru.hibrit_boyut_tespiti(sorgu)
        uc_boyutlar   = self.kural_motoru.uc_kritik_boyutlari(uc_id)
        boyut_listesi = list(dict.fromkeys(tum_boyutlar + uc_boyutlar))

        sistem_prompt = self.kural_motoru.sistem_prompt_uret(uc_id, boyut_listesi)
        baglan = "\n---\n".join(k['metin'][:1200] for k in kaynaklar)
        kullanici = f"Baglam:\n{baglan}\n\nSoru: {sorgu[:500]}\n\nEtik ve hukuki degerlendir."

        llm_yaniti = llm_cagir(sistem_prompt, kullanici)
        skor, puan_skor, genel_puan, risk, uyarilar = \
            self.kural_motoru.kural_dogrulama(llm_yaniti, uc_id, tetiklenen_boyutlar=boyut_listesi)

        benzerlik_dagilimi = [
            (k["meta"].get("baslik", "?"), k["sem_skor"], k["bm25_skor"], k["hibrit_skor"])
            for k in kaynaklar
        ]

        return RAGSonucu(
            sorgu=sorgu, use_case=uc_id,
            tetiklenen_kurallar=boyut_listesi,
            getirilen_kaynaklar=kaynaklar,
            llm_yaniti=llm_yaniti,
            kural_skoru=skor, puan_skoru=puan_skor,
            genel_risk=risk, genel_puan=genel_puan,
            uyari_mesajlari=uyarilar,
            toplam_chunk_sayisi=self.toplam_chunk,
            benzerlik_dagilimi=benzerlik_dagilimi,
            tetiklenen_kural_detaylari=kural_detaylari,
            retrieval_yontemi="Semantik (%.0f%%) + BM25 (%.0f%%)" % (
                SEMANTIC_WEIGHT*100, BM25_WEIGHT*100)
        )
