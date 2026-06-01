#!/usr/bin/env python3
"""
Tradutor direto OpenAI (sem servidor FastAPI intermediário).

Usa gpt-4o-mini com 8 workers paralelos pra traduzir 18k strings em ~15 min
em vez das 2-3h que seria sequencial.

Aplica glossário do servidor (server/glossary.json) — preserva nomes próprios
e força terminologia consistente.

Salva incremental a cada 100 strings, então se algo crashar você não perde
progresso.

Uso:
  export OPENAI_API_KEY="sk-proj-..."
  python translate_openai.py input.json output.json
  python translate_openai.py input.json output.json --model gpt-4o-mini --workers 8

Para retomar (se interrompido):
  python translate_openai.py input.json output.json  # detecta strings já
                                                      # traduzidas e pula
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock

try:
    from openai import OpenAI
except ImportError:
    sys.exit("Falta openai: pip install openai")

# ============================================================================
# Glossário (carrega do server/glossary.json)
# ============================================================================

GLOSSARY_PATH = Path(__file__).parent.parent / "server" / "glossary.json"
try:
    with open(GLOSSARY_PATH, "r", encoding="utf-8") as f:
        GLOSSARY = json.load(f)
except FileNotFoundError:
    GLOSSARY = {"preserve": [], "translate": {}}

PRESERVE = GLOSSARY.get("preserve", [])
TRANSLATE_MAP = GLOSSARY.get("translate", {})


SYSTEM_PROMPT = """Você é tradutor profissional de games, especialista em RPG cyberpunk.
Traduza o texto do inglês pro português brasileiro (PT-BR) com tom natural e cinematográfico.

REGRAS RÍGIDAS:
1. Preserve EXATAMENTE quebras de linha, espaços iniciais/finais.
2. Preserve tags entre {chaves}, [colchetes], <tags>, %s, %d intactas.
3. NUNCA traduza nomes próprios: Adam Jensen, Sarif Industries, Picus, Tai Yong Medical, Pritchard, Belltower, Hengsha, Detroit, Megan Reed, David Sarif, Bill Taggart, Hugh Darrow, Eliza Cassan, FEMA, L.I.M.B., Panchaea.
4. Terminologia FIXA:
   - "Augmented/Augmentation/Augmentations" → "Aumentado/Aumentação/Aumentações"
   - "Hack/Hacking" → "Invadir/Invasão"
   - "Takedown" → "Neutralização"
   - "Praxis Kit" → "Kit Praxis"
   - "Stealth" → "Furtividade"
   - "pocket secretary" → "secretário de bolso"
5. Mantenha tom noir/cyberpunk. "Boss" pode virar "chefe" ou "patrão" conforme contexto.
6. Se for prefixo de speaker (ex: "JF:", "Mary:"), preserve exatamente.
7. Responda APENAS com a tradução. Sem aspas, sem comentários, sem explicações."""


# ============================================================================
# Translator
# ============================================================================

class Translator:
    def __init__(self, model: str = "gpt-4o-mini"):
        self.client = OpenAI()
        self.model = model
        self.lock = Lock()
        self.total_tokens_in = 0
        self.total_tokens_out = 0

    def translate(self, text: str) -> str:
        """Traduz uma string. Aplica pós-processing pra forçar glossário."""
        if not text or text.strip() == "":
            return text

        r = self.client.chat.completions.create(
            model=self.model,
            temperature=0.2,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
        )
        translated = r.choices[0].message.content or ""
        translated = translated.strip()

        # Aplica glossário pra forçar terminologia
        for en, pt in TRANSLATE_MAP.items():
            translated = re.sub(rf"\b{re.escape(en)}\b", pt, translated, flags=re.IGNORECASE)

        # Acumula métricas thread-safe
        with self.lock:
            if r.usage:
                self.total_tokens_in += r.usage.prompt_tokens
                self.total_tokens_out += r.usage.completion_tokens

        return translated


# ============================================================================
# Pipeline
# ============================================================================

def run(input_json: Path, output_json: Path, model: str, workers: int,
        save_every: int):
    with open(input_json, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Quais ainda precisam de tradução
    pending = [s for s in data["strings"]
               if not s["skip"] and s["translated"] is None]
    already_done = sum(1 for s in data["strings"]
                       if s["translated"] is not None)

    print(f"Total: {len(data['strings']):,} strings")
    print(f"Já traduzidas: {already_done:,}")
    print(f"A traduzir agora: {len(pending):,}")
    print(f"Model: {model}, workers: {workers}")
    print()

    if not pending:
        print("Nada a fazer.")
        return

    translator = Translator(model=model)
    save_lock = Lock()
    done_count = [0]  # mutable counter compartilhado entre threads

    t0 = time.time()
    last_save = 0

    def worker(s):
        try:
            s["translated"] = translator.translate(s["original"])
        except Exception as e:
            print(f"  ❌ Erro idx={s['idx']}: {e}", flush=True)
            return None

        with save_lock:
            done_count[0] += 1
            d = done_count[0]
            if d % 25 == 0 or d == len(pending):
                elapsed = time.time() - t0
                rate = d / elapsed if elapsed > 0 else 0
                eta = (len(pending) - d) / rate if rate > 0 else 0
                cost_in = translator.total_tokens_in / 1_000_000 * 0.15
                cost_out = translator.total_tokens_out / 1_000_000 * 0.60
                total_cost = cost_in + cost_out
                print(
                    f"[{d:>6,}/{len(pending):,}] "
                    f"rate={rate:.1f}/s  "
                    f"elapsed={elapsed:.0f}s  "
                    f"eta={eta:.0f}s  "
                    f"tokens_in={translator.total_tokens_in:,}  "
                    f"cost=${total_cost:.3f}",
                    flush=True,
                )
        return s

    # Salvamento incremental
    def save():
        with open(output_json, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # Roda em paralelo
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = [ex.submit(worker, s) for s in pending]

        for fut in as_completed(futures):
            fut.result()
            # Salva periodicamente
            with save_lock:
                if done_count[0] - last_save >= save_every:
                    last_save = done_count[0]
                    save()

    save()

    elapsed = time.time() - t0
    cost_in = translator.total_tokens_in / 1_000_000 * 0.15
    cost_out = translator.total_tokens_out / 1_000_000 * 0.60
    total_cost = cost_in + cost_out
    print()
    print(f"✅ Concluído em {elapsed/60:.1f} min")
    print(f"   Tokens in:  {translator.total_tokens_in:,}  (${cost_in:.3f})")
    print(f"   Tokens out: {translator.total_tokens_out:,}  (${cost_out:.3f})")
    print(f"   Total: ${total_cost:.3f} ≈ R${total_cost * 5.5:.2f}")
    print(f"   Salvo em: {output_json}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input_json", type=Path)
    ap.add_argument("output_json", type=Path)
    ap.add_argument("--model", default="gpt-4o-mini",
                    help="Modelo OpenAI (default: gpt-4o-mini)")
    ap.add_argument("--workers", type=int, default=8,
                    help="Threads paralelas (default: 8)")
    ap.add_argument("--save-every", type=int, default=100,
                    help="Salva JSON a cada N traduções (default: 100)")
    args = ap.parse_args()

    # Se output já existe, retoma de lá
    if args.output_json.exists():
        print(f"Detected existing output, retomando de {args.output_json}")
        import shutil
        # Carrega progresso do output em vez do input
        with open(args.output_json, "r", encoding="utf-8") as f:
            existing = json.load(f)
        # Verifica que é o mesmo input (mesma contagem)
        with open(args.input_json, "r", encoding="utf-8") as f:
            input_data = json.load(f)
        if len(existing["strings"]) == len(input_data["strings"]):
            print(f"  {sum(1 for s in existing['strings'] if s['translated'] is not None):,} já traduzidas, retomando")
            # Usa o output como input pra continuar
            run(args.output_json, args.output_json, args.model, args.workers, args.save_every)
            return

    run(args.input_json, args.output_json, args.model, args.workers,
        args.save_every)


if __name__ == "__main__":
    main()
