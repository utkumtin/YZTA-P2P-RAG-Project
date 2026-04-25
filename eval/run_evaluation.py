"""
RAGAs değerlendirme scripti.
Pipeline kalitesini 4 metrikle ölçer: Faithfulness, Answer Relevancy,
Context Precision, Context Recall.

Kullanım:
    # Canlı pipeline üzerinden (tüm bileşenler çalışıyor olmalı)
    cd backend && python -m eval.run_evaluation

    # Önceden toplanmış sonuçlarla (offline)
    cd backend && python -m eval.run_evaluation --input eval/collected_results.json
"""

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

# Çevre değişkenlerini yükle (backend/.env)
_ENV_PATH = Path(__file__).resolve().parent.parent / "backend" / ".env"
if _ENV_PATH.exists():
    load_dotenv(_ENV_PATH)


from ragas import EvaluationDataset, evaluate
from ragas.llms import llm_factory
from ragas.metrics.collections import (
    AnswerRelevancy,
    ContextPrecisionWithReference,
    ContextRecall,
    Faithfulness,
)

# Proje kök dizinini Python path'e ekle (backend dışından çalıştırma durumu).
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# =========================================================================
# HEDEF METRİK EŞİKLERİ
# =========================================================================
THRESHOLDS = {
    "faithfulness": 0.85,
    "answer_relevancy": 0.80,
    "context_precision": 0.80,
    "context_recall": 0.75,
}

# Test veri seti dosyası
_DATASET_PATH = Path(__file__).resolve().parent / "test_dataset.json"

# Sonuçların kaydedileceği dizin
_RESULTS_DIR = Path(__file__).resolve().parent / "results"


def load_test_dataset(path: Path | None = None) -> list[dict]:
    """
    Test veri setini JSON dosyasından yükler.

    Returns:
        list[dict]: Her eleman {question, ground_truth, source_doc, source_page}
    """
    dataset_path = path or _DATASET_PATH

    if not dataset_path.exists():
        raise FileNotFoundError(
            f"Test veri seti bulunamadı: {dataset_path}\n"
            "Lütfen eval/test_dataset.json dosyasını oluşturun."
        )

    with open(dataset_path, encoding="utf-8") as f:
        dataset = json.load(f)

    if not dataset:
        raise ValueError("Test veri seti boş.")

    return dataset


async def collect_pipeline_results(
    test_data: list[dict],
    session_id: str = "eval-session",
) -> list[dict]:
    """
    Her test sorusunu RAG pipeline'ından geçirir ve sonuçları toplar.

    Gereken bileşenler çalışır durumda olmalı:
    - Qdrant (vektör DB)
    - Embedding modeli
    - Reranker
    - LLM

    Returns:
        list[dict]: RAGAs formatında sonuçlar
            {user_input, response, retrieved_contexts, reference}
    """
    from app.core.embedder import Embedder
    from app.core.llm_client import create_llm_client
    from app.core.rag_pipeline import RAGPipeline
    from app.core.reranker import Reranker
    from app.core.vector_store import VectorStore

    # Bileşenleri başlat
    embedder = Embedder()
    vector_store = VectorStore(
        host=os.getenv("QDRANT_HOST", "localhost"),
        port=int(os.getenv("QDRANT_PORT", "6333")),
    )
    reranker = Reranker()
    llm_client = create_llm_client(
        provider=os.getenv("LLM_PROVIDER", "groq"),
        api_key=os.getenv("GROQ_API_KEY", "") or os.getenv("GOOGLE_API_KEY", ""),
    )

    pipeline = RAGPipeline(
        embedder=embedder,
        vector_store=vector_store,
        reranker=reranker,
        llm_client=llm_client,
        cache=None,  # Değerlendirmede cache devre dışı
    )

    results = []
    total = len(test_data)

    for i, item in enumerate(test_data, 1):
        question = item["question"]
        print(f"  [{i}/{total}] {question}")

        try:
            # Retrieval + Reranking → parent chunk'ları getir
            context_chunks = await pipeline._retrieve_and_resolve(question, session_id)

            # Context metinlerini çıkar
            contexts = [c.get("text", "") for c in context_chunks]

            # LLM cevabını al
            answer, _ = await pipeline.query(question, session_id)

        except Exception as e:
            print(f"    ⚠ Hata: {e}")
            answer = ""
            contexts = []

        results.append(
            {
                "user_input": question,
                "response": answer,
                "retrieved_contexts": contexts,
                "reference": item["ground_truth"],
            }
        )

    return results


def run_ragas_evaluation(collected_results: list[dict]) -> dict:
    """
    RAGAs ile değerlendirme çalıştırır.

    RAGAs'ın kendi LLM'i (evaluator LLM) metrikleri hesaplamak için gerekir.
    Google Gemini kullanılır — GOOGLE_API_KEY ortam değişkeni zorunlu.

    Args:
        collected_results: Pipeline'dan toplanan sonuçlar (RAGAs formatında)

    Returns:
        dict: Metrik sonuçları {faithfulness, answer_relevancy, ...}
    """
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise OSError(
            "GOOGLE_API_KEY ortam değişkeni gerekli.\n"
            "RAGAs metrikleri hesaplamak için bir evaluator LLM lazım.\n"
            "export GOOGLE_API_KEY='...'"
        )

    # ragas 0.4.x — native Google Gemini desteği
    from google import genai

    client = genai.Client(api_key=api_key)
    evaluator_llm = llm_factory(
        model="gemini-2.0-flash",
        provider="google",
        client=client,
    )

    # Metrikleri tanımla
    metrics = [
        Faithfulness(llm=evaluator_llm),
        AnswerRelevancy(llm=evaluator_llm),
        ContextPrecisionWithReference(llm=evaluator_llm),
        ContextRecall(llm=evaluator_llm),
    ]

    # EvaluationDataset oluştur
    eval_dataset = EvaluationDataset.from_list(collected_results)

    print("\n📊 RAGAs değerlendirmesi çalıştırılıyor...")
    result = evaluate(dataset=eval_dataset, metrics=metrics)

    return result


def print_results(result, thresholds: dict = THRESHOLDS):
    """Sonuçları formatlı şekilde yazdırır, hedef eşiklerle karşılaştırır."""
    # ragas evaluate() dönüşü dict-like erişim sağlar
    scores = result.scores if hasattr(result, "scores") else result

    # Metrik adlarını normalize et
    metric_map = {
        "faithfulness": "Faithfulness",
        "answer_relevancy": "Answer Relevancy",
        "context_precision": "Context Precision",
        "context_recall": "Context Recall",
    }

    print("\n" + "=" * 60)
    print("   RAG DEĞERLENDİRME SONUÇLARI")
    print("=" * 60)

    all_pass = True
    result_dict = {}

    for key, display_name in metric_map.items():
        score = scores.get(key)
        if score is None:
            # ragas 0.4.x çıktısında metrik sınıf adıyla gelebilir
            alt_keys = {
                "answer_relevancy": "answer_relevancy",
                "context_precision": "context_precision_with_reference",
                "context_recall": "context_recall",
            }
            alt = alt_keys.get(key)
            if alt:
                score = scores.get(alt)

        if score is None:
            print(f"  {display_name}: N/A")
            continue

        threshold = thresholds.get(key, 0.0)
        status = "✅" if score >= threshold else "❌"
        if score < threshold:
            all_pass = False

        print(f"  {status} {display_name}: {score:.3f}  (hedef ≥ {threshold})")
        result_dict[key] = score

    print("=" * 60)
    if all_pass:
        print("  🎉 Tüm metrikler hedef eşikleri karşılıyor!")
    else:
        print("  ⚠️  Bazı metrikler hedef eşiğin altında.")
    print()

    return result_dict


def save_results(result_dict: dict, collected_results: list[dict]):
    """Sonuçları JSON dosyasına kaydeder."""
    _RESULTS_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    output = {
        "timestamp": datetime.now().isoformat(),
        "thresholds": THRESHOLDS,
        "scores": result_dict,
        "sample_count": len(collected_results),
        "details": collected_results,
    }

    output_path = _RESULTS_DIR / f"eval_{timestamp}.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"📁 Sonuçlar kaydedildi: {output_path}")


async def main():
    parser = argparse.ArgumentParser(description="RAGAs RAG Değerlendirmesi")
    parser.add_argument(
        "--input",
        type=str,
        default=None,
        help="Önceden toplanmış sonuçlar JSON dosyası (offline mod)",
    )
    parser.add_argument(
        "--dataset",
        type=str,
        default=None,
        help="Özel test veri seti dosyası",
    )
    parser.add_argument(
        "--session-id",
        type=str,
        default="eval-session",
        help="Pipeline sorguları için session ID",
    )
    parser.add_argument(
        "--collect-only",
        action="store_true",
        help="Sadece pipeline sonuçlarını topla, RAGAs değerlendirmesi yapma",
    )
    args = parser.parse_args()

    print("🔍 RAG Değerlendirme Pipeline'ı")
    print("-" * 40)

    # 1. Sonuçları topla veya dosyadan yükle
    if args.input:
        print(f"📂 Önceden toplanmış sonuçlar yükleniyor: {args.input}")
        with open(args.input, encoding="utf-8") as f:
            data = json.load(f)

        # Eğer kayıtlı sonuç dosyası ise 'details' anahtarına bak
        collected_results = data.get("details", data)
    else:
        dataset_path = Path(args.dataset) if args.dataset else None
        test_data = load_test_dataset(dataset_path)
        print(f"📋 Test veri seti yüklendi: {len(test_data)} soru")
        print("🔄 Pipeline üzerinden sonuçlar toplanıyor...\n")

        collected_results = await collect_pipeline_results(test_data, session_id=args.session_id)

    # Toplanan sonuçları kaydet (collect-only modunda RAGAs çalıştırılmaz)
    if args.collect_only:
        _RESULTS_DIR.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = _RESULTS_DIR / f"collected_{timestamp}.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(collected_results, f, ensure_ascii=False, indent=2)
        print(f"\n📁 Pipeline sonuçları kaydedildi: {output_path}")
        print("Değerlendirme için: python -m eval.run_evaluation --input " + str(output_path))
        return

    # 2. RAGAs değerlendirmesi
    result = run_ragas_evaluation(collected_results)

    # 3. Sonuçları yazdır ve kaydet
    result_dict = print_results(result)
    save_results(result_dict, collected_results)


if __name__ == "__main__":
    asyncio.run(main())
