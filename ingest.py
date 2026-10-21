"""
ingest.py - v3 (MemoryError düzeltmesi)
"""

import os
import re
import chromadb
from sentence_transformers import SentenceTransformer

BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
KB_DIR        = os.path.join(BASE_DIR, "knowledge_base")
CHROMA_DIR    = os.path.join(BASE_DIR, "chroma_db")
COLLECTION    = "saglik_yz_etik"
MODEL_NAME    = "paraphrase-multilingual-MiniLM-L12-v2"
CHUNK_SIZE    = 800
CHUNK_OVERLAP = 150


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list:
    """Cümle sınırına duyarlı chunk'lama — sonsuz döngü korumalı."""
    SENTENCE_ENDINGS = ["\n\n", ".\n", ". ", "? ", "! ", ";\n"]

    chunks = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = min(start + size, text_len)

        if end < text_len:
            best = -1
            for sep in SENTENCE_ENDINGS:
                pos = text.rfind(sep, start + 80, end)
                if pos > best:
                    best = pos + len(sep)
            if best > start + 80:
                end = best

        chunk = text[start:end].strip()
        if len(chunk) > 50:
            chunks.append(chunk)

        # Sonsuz döngü koruması: start mutlaka ilerlemeli
        new_start = end - overlap
        if new_start <= start:
            new_start = start + max(size // 2, 1)
        start = new_start

    return chunks


def temizle_metadata_satirlari(metin: str) -> str:
    """## BELGE N:, KAYNAK:, KATEGORİ:, KAPSAM: satırlarını metinden çıkar."""
    temiz = []
    for satir in metin.split("\n"):
        s = satir.strip()
        if re.match(r"^##\s*BELGE\s+\d+:", s, re.IGNORECASE):
            continue
        if re.match(r"^(KAYNAK|KATEGORI|KATEGORİ|KAPSAM)\s*:", s, re.IGNORECASE):
            continue
        temiz.append(satir)
    return "\n".join(temiz)


def temizle_chunk_basi(chunk: str) -> str:
    """Chunk başındaki kırık cümleyi temizle (küçük harfle başlıyorsa ilk tam cümleye atla)."""
    satir = chunk.lstrip()
    if not satir:
        return chunk
    # İlk karakter küçük harf veya bağlaç/noktalama ile başlıyorsa kırık cümle
    ilk = satir[0]
    if ilk.islower() or ilk in (',', ';', 've', '-'):
        # İlk büyük harf başlangıcını bul
        for sep in [". ", "! ", "? ", "\n"]:
            idx = satir.find(sep)
            if idx != -1 and idx < 200:
                kalan = satir[idx + len(sep):].strip()
                if kalan and kalan[0].isupper():
                    return kalan
    return chunk


def parse_belge_meta(text: str, filename: str) -> list:
    bolumler = re.split(r"(?=## BELGE \d+:)", text)
    sonuclar = []
    for bolum in bolumler:
        bolum = bolum.strip()
        if not bolum:
            continue
        baslik_m   = re.search(r"## BELGE \d+:\s*(.+)", bolum)
        kaynak_m   = re.search(r"KAYNAK:\s*(.+)", bolum)
        kategori_m = re.search(r"KATEGORİ:\s*(.+)", bolum)
        kapsam_m   = re.search(r"KAPSAM:\s*(.+)", bolum)

        # Metadata satırlarını metinden çıkar, sonra chunk'la
        bolum_temiz = temizle_metadata_satirlari(bolum)
        chunks = chunk_text(bolum_temiz)

        for i, chunk in enumerate(chunks):
            # Chunk başındaki kırık cümleyi düzelt
            chunk = temizle_chunk_basi(chunk)
            if len(chunk) < 50:
                continue
            sonuclar.append({
                "text": chunk,
                "meta": {
                    "dosya":    filename,
                    "baslik":   baslik_m.group(1).strip()   if baslik_m   else filename,
                    "kaynak":   kaynak_m.group(1).strip()   if kaynak_m   else "Bilinmiyor",
                    "kategori": kategori_m.group(1).strip() if kategori_m else "Genel",
                    "kapsam":   kapsam_m.group(1).strip()   if kapsam_m   else "",
                    "chunk_no": i
                }
            })
    return sonuclar


def ingest():
    print("Bilgi tabani yukleniyor...")
    print(f"  -> Embedding modeli : {MODEL_NAME}")
    print(f"  -> Chunk boyutu     : {CHUNK_SIZE} karakter")
    print(f"  -> Ortusme          : {CHUNK_OVERLAP} karakter")
    model = SentenceTransformer(MODEL_NAME)

    client = chromadb.PersistentClient(path=CHROMA_DIR)
    try:
        client.delete_collection(COLLECTION)
        print("  -> Mevcut koleksiyon silindi.")
    except Exception:
        pass

    collection = client.create_collection(
        name=COLLECTION,
        metadata={"hnsw:space": "cosine"}
    )

    tum_chunks = []
    for fname in os.listdir(KB_DIR):
        if fname.endswith(".txt"):
            fpath = os.path.join(KB_DIR, fname)
            with open(fpath, "r", encoding="utf-8") as f:
                icerik = f.read()
            parsed = parse_belge_meta(icerik, fname)
            tum_chunks.extend(parsed)
            print(f"  -> {fname}: {len(parsed)} chunk")

    if not tum_chunks:
        print("Hic belge bulunamadi!")
        return

    print(f"  -> Toplam {len(tum_chunks)} chunk embed ediliyor...")
    metinler = [c["text"] for c in tum_chunks]
    embedler = model.encode(metinler, show_progress_bar=True, batch_size=32)

    collection.add(
        ids=[f"chunk_{i}" for i in range(len(tum_chunks))],
        embeddings=embedler.tolist(),
        documents=metinler,
        metadatas=[c["meta"] for c in tum_chunks]
    )
    print(f"\nTAMAM: {len(tum_chunks)} chunk ChromaDB'ye yuklendi -> {CHROMA_DIR}")


if __name__ == "__main__":
    ingest()
