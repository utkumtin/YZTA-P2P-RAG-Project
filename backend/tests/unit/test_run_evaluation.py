"""
eval/run_evaluation.py modülü için birim testleri.

Pipeline'a veya LLM'e bağımlı olmayan fonksiyonları test eder:
- load_test_dataset: Veri seti yükleme ve validasyon
- print_results: Sonuç formatlama ve eşik karşılaştırması
- save_results: Dosyaya kaydetme
"""

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# eval dizini proje kök altında; backend/tests'ten çalıştırıldığında
# path ayarı gerekir.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from eval.run_evaluation import (  # noqa: E402
    THRESHOLDS,
    load_test_dataset,
    print_results,
    save_results,
)

# =========================================================================
# FIXTURES
# =========================================================================


@pytest.fixture
def sample_dataset():
    """Geçerli test veri seti."""
    return [
        {
            "question": "Sözleşmenin fesih cezası nedir?",
            "ground_truth": "Yıllık bedelin %20'si.",
            "source_doc": "sozlesme.pdf",
            "source_page": 7,
        },
        {
            "question": "Yıllık izin kaç gün?",
            "ground_truth": "14 gün.",
            "source_doc": "yonetmelik.docx",
            "source_page": None,
        },
    ]


@pytest.fixture
def sample_collected_results():
    """Pipeline'dan toplanmış örnek sonuçlar."""
    return [
        {
            "user_input": "Fesih cezası nedir?",
            "response": "Yıllık bedelin %20'si oranında ceza uygulanır.",
            "retrieved_contexts": ["Madde 12: Fesih halinde %20 ceza..."],
            "reference": "Yıllık bedelin %20'si.",
        },
    ]


@pytest.fixture
def temp_dataset_file(sample_dataset):
    """Geçici test veri seti dosyası oluşturur."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as f:
        json.dump(sample_dataset, f, ensure_ascii=False)
        return Path(f.name)


# =========================================================================
# load_test_dataset TESTLERI
# =========================================================================


class TestLoadTestDataset:
    def test_loads_valid_dataset(self, temp_dataset_file, sample_dataset):
        """Geçerli JSON dosyasını başarıyla yükler."""
        result = load_test_dataset(temp_dataset_file)
        assert len(result) == len(sample_dataset)
        assert result[0]["question"] == sample_dataset[0]["question"]

    def test_raises_on_missing_file(self):
        """Dosya yoksa FileNotFoundError fırlatır."""
        with pytest.raises(FileNotFoundError):
            load_test_dataset(Path("/nonexistent/path.json"))

    def test_raises_on_empty_dataset(self):
        """Boş liste durumunda ValueError fırlatır."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump([], f)
            path = Path(f.name)

        with pytest.raises(ValueError, match="boş"):
            load_test_dataset(path)

    def test_preserves_turkish_characters(self, temp_dataset_file):
        """Türkçe karakterler bozulmadan yüklenir."""
        result = load_test_dataset(temp_dataset_file)
        assert "ö" in result[0]["question"]  # "Sözleşmenin"
        assert "ş" in result[0]["question"]

    def test_handles_null_source_page(self, temp_dataset_file):
        """source_page: null değeri korunur."""
        result = load_test_dataset(temp_dataset_file)
        assert result[1]["source_page"] is None


# =========================================================================
# print_results TESTLERI
# =========================================================================


class TestPrintResults:
    def test_all_metrics_pass(self, capsys):
        """Tüm metrikler eşiğin üstündeyse başarı mesajı yazdırır."""
        mock_result = {
            "faithfulness": 0.90,
            "answer_relevancy": 0.85,
            "context_precision": 0.82,
            "context_recall": 0.80,
        }
        result_dict = print_results(mock_result, THRESHOLDS)

        captured = capsys.readouterr()
        assert "✅" in captured.out
        assert "Tüm metrikler" in captured.out
        assert result_dict["faithfulness"] == 0.90

    def test_some_metrics_fail(self, capsys):
        """Eşiğin altındaki metrikler ❌ ile işaretlenir."""
        mock_result = {
            "faithfulness": 0.60,  # ≥ 0.85 gerekli → FAIL
            "answer_relevancy": 0.85,
            "context_precision": 0.82,
            "context_recall": 0.80,
        }
        result_dict = print_results(mock_result, THRESHOLDS)

        captured = capsys.readouterr()
        assert "❌" in captured.out
        assert "Bazı metrikler" in captured.out
        assert result_dict["faithfulness"] == 0.60

    def test_handles_alternative_key_names(self, capsys):
        """ragas 0.4.x'in farklı metrik key isimleri desteklenir."""
        mock_result = {
            "faithfulness": 0.90,
            "answer_relevancy": 0.85,
            "context_precision_with_reference": 0.82,  # alternatif key
            "context_recall": 0.80,
        }
        result_dict = print_results(mock_result, THRESHOLDS)
        assert "context_precision" in result_dict


# =========================================================================
# save_results TESTLERI
# =========================================================================


class TestSaveResults:
    def test_saves_json_file(self, sample_collected_results):
        """Sonuçlar JSON dosyasına kaydedilir."""
        result_dict = {"faithfulness": 0.90, "answer_relevancy": 0.85}

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch(
                "eval.run_evaluation._RESULTS_DIR", Path(tmpdir)
            ):
                save_results(result_dict, sample_collected_results)

            # En az bir dosya oluşmuş olmalı
            files = list(Path(tmpdir).glob("eval_*.json"))
            assert len(files) == 1

            with open(files[0], encoding="utf-8") as f:
                saved = json.load(f)

            assert saved["scores"] == result_dict
            assert saved["sample_count"] == 1
            assert "timestamp" in saved

    def test_preserves_turkish_in_output(self, sample_collected_results):
        """Kayıt dosyasında Türkçe karakterler korunur."""
        result_dict = {"faithfulness": 0.90}

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch(
                "eval.run_evaluation._RESULTS_DIR", Path(tmpdir)
            ):
                save_results(result_dict, sample_collected_results)

            files = list(Path(tmpdir).glob("eval_*.json"))
            content = files[0].read_text(encoding="utf-8")
            # ensure_ascii=False sayesinde Türkçe korunur
            assert "%" in content or "ceza" in content


# =========================================================================
# TEST DATASET CONTENT VALIDATION
# =========================================================================


class TestDatasetContent:
    """eval/test_dataset.json dosyasının içeriğini doğrular."""

    def test_minimum_20_questions(self):
        """En az 20 soru-cevap çifti var."""
        dataset = load_test_dataset(_PROJECT_ROOT / "eval" / "test_dataset.json")
        assert len(dataset) >= 20

    def test_all_entries_have_required_fields(self):
        """Her giriş zorunlu alanları içerir."""
        dataset = load_test_dataset(_PROJECT_ROOT / "eval" / "test_dataset.json")
        required = {"question", "ground_truth", "source_doc", "source_page"}
        for i, item in enumerate(dataset):
            missing = required - set(item.keys())
            assert not missing, f"Giriş {i}: eksik alanlar: {missing}"

    def test_questions_are_non_empty(self):
        """Sorular boş değil."""
        dataset = load_test_dataset(_PROJECT_ROOT / "eval" / "test_dataset.json")
        for i, item in enumerate(dataset):
            assert item["question"].strip(), f"Giriş {i}: boş soru"
            assert item["ground_truth"].strip(), f"Giriş {i}: boş ground_truth"
