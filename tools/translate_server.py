"""
Servidor local de tradução EN -> PT-BR para o projeto DXHR Wii U.

Roda no Mac via:
    uvicorn translate_server:app --host 0.0.0.0 --port 8765

Endpoints:
    POST /translate           — recebe lista de strings, devolve traduções
    GET  /health              — sanity check
    GET  /cache/stats         — quantas strings em cache, hits/misses
    POST /cache/clear         — limpa cache (use com cuidado)

Backends (env var TRANSLATOR_BACKEND):
    nllb       (default) — Meta NLLB-200 local, gratuito, qualidade boa pra game
    openai     — usa gpt-4o-mini (precisa OPENAI_API_KEY)
    deepl      — usa DeepL API (precisa DEEPL_API_KEY)

O servidor mantém um cache em disco (cache.jsonl) com hash de cada string
pra nunca traduzir duas vezes a mesma frase. Isso economiza tempo gigante
quando o jogo tem milhares de strings repetidas (UI, hints, etc.).

Glossário (glossary.json) protege nomes próprios e fixa terminologia.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from pathlib import Path
from typing import Optional

print("[startup] carregando dependencias (fastapi/uvicorn)... isso pode levar 5-20s na primeira vez, aguarde.", flush=True)

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

print("[startup] dependencias OK. O modelo NLLB so sera baixado/carregado na PRIMEIRA traducao.", flush=True)

# ============================================================================
# Configuração
# ============================================================================

ROOT = Path(__file__).parent
CACHE_PATH = ROOT / "cache.jsonl"
GLOSSARY_PATH = ROOT / "glossary.json"

BACKEND = os.environ.get("TRANSLATOR_BACKEND", "nllb").lower()
SOURCE_LANG = os.environ.get("SOURCE_LANG", "eng_Latn")  # NLLB code
TARGET_LANG = os.environ.get("TARGET_LANG", "por_Latn")  # NLLB code
HF_MODEL = os.environ.get("NLLB_MODEL", "facebook/nllb-200-distilled-600M")

# ============================================================================
# Glossário
# ============================================================================

def load_glossary() -> dict:
    if not GLOSSARY_PATH.exists():
        return {"preserve": [], "translate": {}}
    with open(GLOSSARY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


GLOSSARY = load_glossary()
PRESERVE = sorted(GLOSSARY.get("preserve", []), key=len, reverse=True)
TRANSLATE_MAP = GLOSSARY.get("translate", {})

PRESERVE_TOKEN = "§§{idx}§§"  # placeholder que sobrevive ao modelo


def protect(text: str) -> tuple[str, list[str]]:
    """Substitui termos preserved por placeholders. Retorna texto + lista."""
    preserved = []
    for term in PRESERVE:
        if term in text:
            idx = len(preserved)
            preserved.append(term)
            text = text.replace(term, PRESERVE_TOKEN.format(idx=idx))
    return text, preserved


def restore(text: str, preserved: list[str]) -> str:
    for idx, term in enumerate(preserved):
        text = text.replace(PRESERVE_TOKEN.format(idx=idx), term)
    return text


def apply_glossary_post(text: str) -> str:
    """Aplica substituições do mapa translate APÓS a tradução do modelo,
    pra forçar a terminologia consistente (ex: 'Aumentação' não 'Aumento')."""
    for en, pt in TRANSLATE_MAP.items():
        # Substituição case-sensitive — confia no que está no JSON
        text = re.sub(rf"\b{re.escape(en)}\b", pt, text)
    return text


# ============================================================================
# Cache
# ============================================================================

class Cache:
    def __init__(self, path: Path):
        self.path = path
        self.data: dict[str, str] = {}
        self.hits = 0
        self.misses = 0
        self._load()

    def _load(self):
        if not self.path.exists():
            return
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    self.data[obj["h"]] = obj["t"]
                except Exception:
                    pass

    def _key(self, src: str) -> str:
        return hashlib.sha256(
            f"{BACKEND}|{SOURCE_LANG}|{TARGET_LANG}|{src}".encode("utf-8")
        ).hexdigest()[:24]

    def get(self, src: str) -> Optional[str]:
        v = self.data.get(self._key(src))
        if v is not None:
            self.hits += 1
        else:
            self.misses += 1
        return v

    def put(self, src: str, tgt: str):
        h = self._key(src)
        self.data[h] = tgt
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"h": h, "src": src, "t": tgt}, ensure_ascii=False) + "\n")

    def clear(self):
        self.data.clear()
        self.hits = 0
        self.misses = 0
        if self.path.exists():
            self.path.unlink()


CACHE = Cache(CACHE_PATH)

# ============================================================================
# Backends
# ============================================================================

class Backend:
    name = "base"
    def translate_batch(self, texts: list[str]) -> list[str]:
        raise NotImplementedError


class NLLBBackend(Backend):
    """Meta NLLB-200 rodando local. Apple Silicon usa MPS automaticamente."""
    name = "nllb"

    def __init__(self):
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
        import torch
        self.torch = torch
        self.device = (
            "mps" if torch.backends.mps.is_available()
            else "cuda" if torch.cuda.is_available()
            else "cpu"
        )
        print(f"[NLLB] carregando {HF_MODEL} em {self.device}…")
        self.tok = AutoTokenizer.from_pretrained(HF_MODEL, src_lang=SOURCE_LANG)
        self.model = AutoModelForSeq2SeqLM.from_pretrained(HF_MODEL).to(self.device)
        self.tgt_id = self.tok.convert_tokens_to_ids(TARGET_LANG)
        print(f"[NLLB] pronto. target_token_id={self.tgt_id}")

    def translate_batch(self, texts: list[str]) -> list[str]:
        if not texts:
            return []
        inputs = self.tok(texts, return_tensors="pt", padding=True, truncation=True, max_length=512).to(self.device)
        with self.torch.no_grad():
            out = self.model.generate(
                **inputs,
                forced_bos_token_id=self.tgt_id,
                max_new_tokens=400,
                num_beams=2,  # reduzido de 4 — corta o pico de memoria pela metade
            )
        result = self.tok.batch_decode(out, skip_special_tokens=True)
        # Libera memoria da GPU/MPS entre lotes pra evitar acumulo que travava o Mac
        if self.device == "mps":
            self.torch.mps.empty_cache()
        return result


class OpenAIBackend(Backend):
    """OpenAI backend com requests concorrentes via ThreadPoolExecutor.
    Acelera ~10x vs sequencial. ~15 min pra traduzir 18k strings."""
    name = "openai"

    SYSTEM_PROMPT = (
        "Você é tradutor profissional de games. Traduza do inglês para o português do Brasil. "
        "Preserve EXATAMENTE quebras de linha, espaços iniciais/finais, tags entre colchetes ou chaves "
        "({BUTTON_X}, [NAME], etc.) e placeholders %s/%d. Mantenha tom cyberpunk/noir do Deus Ex. "
        "Não adicione comentários, só a tradução."
    )

    def __init__(self):
        from openai import OpenAI
        from concurrent.futures import ThreadPoolExecutor
        self.client = OpenAI()
        self.model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        self.max_workers = int(os.environ.get("OPENAI_CONCURRENCY", "10"))
        self._executor = ThreadPoolExecutor(max_workers=self.max_workers)
        print(f"[openai] modelo={self.model} concurrency={self.max_workers}")

    def _translate_one(self, t: str) -> str:
        r = self.client.chat.completions.create(
            model=self.model,
            temperature=0.1,
            messages=[
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": t},
            ],
        )
        return r.choices[0].message.content or ""

    def translate_batch(self, texts: list[str]) -> list[str]:
        if not texts:
            return []
        return list(self._executor.map(self._translate_one, texts))


class DeepLBackend(Backend):
    name = "deepl"
    def __init__(self):
        import deepl
        self.client = deepl.Translator(os.environ["DEEPL_API_KEY"])

    def translate_batch(self, texts: list[str]) -> list[str]:
        res = self.client.translate_text(texts, source_lang="EN", target_lang="PT-BR", preserve_formatting=True)
        return [r.text for r in res] if isinstance(res, list) else [res.text]


# ============================================================================
# App
# ============================================================================

app = FastAPI(title="DXHR Translator", version="0.1")

BACKEND_INSTANCE: Optional[Backend] = None

def get_backend() -> Backend:
    global BACKEND_INSTANCE
    if BACKEND_INSTANCE is None:
        if BACKEND == "nllb":
            BACKEND_INSTANCE = NLLBBackend()
        elif BACKEND == "openai":
            BACKEND_INSTANCE = OpenAIBackend()
        elif BACKEND == "deepl":
            BACKEND_INSTANCE = DeepLBackend()
        else:
            raise RuntimeError(f"backend desconhecido: {BACKEND}")
    return BACKEND_INSTANCE


class TranslateRequest(BaseModel):
    texts: list[str] = Field(..., description="Strings a traduzir (lote)")
    use_cache: bool = True
    use_glossary: bool = True


class TranslateResponse(BaseModel):
    translations: list[str]
    cache_hits: int
    backend: str
    elapsed_ms: int


@app.on_event("startup")
def _warmup():
    """Carrega o modelo no boot (nao na 1a requisicao) pra evitar timeout do cliente."""
    if os.environ.get("WARMUP", "1") == "1":
        try:
            print("[startup] aquecendo o modelo (carga unica)...", flush=True)
            get_backend()
            print("[startup] modelo aquecido e pronto.", flush=True)
        except Exception as e:
            print(f"[startup] warmup falhou (sera carregado na 1a traducao): {e}", flush=True)


@app.get("/health")
def health():
    return {"ok": True, "backend": BACKEND, "src": SOURCE_LANG, "tgt": TARGET_LANG}


@app.get("/cache/stats")
def cache_stats():
    return {"entries": len(CACHE.data), "hits": CACHE.hits, "misses": CACHE.misses}


@app.post("/cache/clear")
def cache_clear():
    CACHE.clear()
    return {"ok": True}


@app.post("/translate", response_model=TranslateResponse)
def translate(req: TranslateRequest):
    t0 = time.time()
    backend = get_backend()

    results: list[Optional[str]] = [None] * len(req.texts)
    to_translate_idx: list[int] = []
    to_translate_src: list[str] = []
    preserved_lists: list[list[str]] = [[] for _ in req.texts]

    # Pass 1: cache + protect
    hits = 0
    for i, src in enumerate(req.texts):
        if req.use_cache:
            cached = CACHE.get(src)
            if cached is not None:
                results[i] = cached
                hits += 1
                continue
        if req.use_glossary:
            protected, plist = protect(src)
            preserved_lists[i] = plist
            to_translate_src.append(protected)
        else:
            to_translate_src.append(src)
        to_translate_idx.append(i)

    # Pass 2: traduz o que ficou em lote
    if to_translate_src:
        try:
            outs = backend.translate_batch(to_translate_src)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"backend error: {e}")
        for k, i in enumerate(to_translate_idx):
            tgt = outs[k]
            if req.use_glossary:
                tgt = restore(tgt, preserved_lists[i])
                tgt = apply_glossary_post(tgt)
            results[i] = tgt
            if req.use_cache:
                CACHE.put(req.texts[i], tgt)

    return TranslateResponse(
        translations=[r or "" for r in results],
        cache_hits=hits,
        backend=backend.name,
        elapsed_ms=int((time.time() - t0) * 1000),
    )


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8765))
    print(f"[startup] subindo servidor em http://localhost:{port}  (Ctrl-C para parar)", flush=True)
    print("[startup] quando aparecer 'Uvicorn running on...', deixe ESTE terminal aberto e use o outro terminal.", flush=True)
    uvicorn.run(app, host="0.0.0.0", port=port)
