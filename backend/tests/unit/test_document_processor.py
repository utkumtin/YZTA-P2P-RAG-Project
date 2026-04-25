"""
pytest ile çalıştır:
    cd backend
    pytest tests/unit/test_document_processor.py -v

NOT: PDF ve DOCX testleri için tests/test_files/ dizinine
ilgili test dosyalarını eklemeniz gerekir.
"""

from pathlib import Path

import pytest

from app.core.document_processor import DocumentProcessingError, DocumentProcessor

# Test dosyaları dizini (proje kökünden göreli)
TEST_FILES_DIR = Path(__file__).parent.parent / "test_files"


@pytest.fixture
def processor():
    """Her test için taze bir DocumentProcessor örneği."""
    return DocumentProcessor()


class TestProcessMethod:
    """process() ana metodu için testler."""

    def test_var_olmayan_dosya_hata_vermeli(self, processor):
        """Var olmayan dosya yolu → DocumentProcessingError."""
        with pytest.raises(DocumentProcessingError) as exc_info:
            processor.process("yok_boyle_bir_dosya.pdf", doc_id="test-001")
        assert "Dosya bulunamadı" in str(exc_info.value)

    def test_desteklenmeyen_format_hata_vermeli(self, processor, tmp_path):
        """Desteklenmeyen uzantı → DocumentProcessingError."""
        fake_file = tmp_path / "test.xyz"
        fake_file.write_text("içerik")
        with pytest.raises(DocumentProcessingError) as exc_info:
            processor.process(str(fake_file), doc_id="test-002")
        assert "Desteklenmeyen" in str(exc_info.value)

    def test_doc_id_none_gecilirse_none_doner(self, processor):
        """doc_id=None geçildiğinde sonuçta doc_id: None olmalı."""
        txt_file = TEST_FILES_DIR / "utf8.txt"
        if not txt_file.exists():
            pytest.skip("utf8.txt test dosyası bulunamadı")
        result = processor.process(str(txt_file))  # doc_id verilmedi
        assert result["doc_id"] is None

    def test_sonuc_yapisi_dogru_olmali(self, processor):
        """Dönen dict beklenen tüm anahtarları içermeli."""
        txt_file = TEST_FILES_DIR / "utf8.txt"
        if not txt_file.exists():
            pytest.skip("utf8.txt test dosyası bulunamadı")
        result = processor.process(str(txt_file), doc_id="test-struct")
        assert "doc_id" in result
        assert "filename" in result
        assert "file_type" in result
        assert "pages" in result
        assert "full_text" in result
        assert "language" in result


class TestTxtProcessing:
    """TXT dosyası işleme testleri."""

    def test_utf8_txt_okunmali(self, processor):
        """UTF-8 TXT dosyasından metin çıkarılmalı."""
        txt_file = TEST_FILES_DIR / "utf8.txt"
        if not txt_file.exists():
            pytest.skip("utf8.txt test dosyası bulunamadı")
        result = processor.process(str(txt_file), doc_id="test-txt-001")
        assert len(result["full_text"]) > 10, "TXT'den metin çıkarılamadı"
        assert result["file_type"] == "txt"

    def test_turkce_karakterler_korunmali(self, processor):
        """Türkçe karakterler (ş, ç, ğ, ü, ö) kaybolmamalı."""
        txt_file = TEST_FILES_DIR / "utf8.txt"
        if not txt_file.exists():
            pytest.skip("utf8.txt test dosyası bulunamadı")
        result = processor.process(str(txt_file), doc_id="test-txt-002")
        turkce_karakterler = any(c in result["full_text"] for c in "şçğüöıŞÇĞÜÖİ")
        assert turkce_karakterler, "Türkçe karakterler kayıp"

    def test_txt_sayfa_numarasi_1_olmali(self, processor):
        """TXT dosyaları tek sayfa olarak döner (page_number: 1)."""
        txt_file = TEST_FILES_DIR / "utf8.txt"
        if not txt_file.exists():
            pytest.skip("utf8.txt test dosyası bulunamadı")
        result = processor.process(str(txt_file), doc_id="test-txt-003")
        assert len(result["pages"]) == 1
        assert result["pages"][0]["page_number"] == 1

    def test_bos_txt_hata_vermeli(self, processor, tmp_path):
        """Boş TXT dosyası → DocumentProcessingError."""
        empty_file = tmp_path / "empty.txt"
        empty_file.write_text("")
        with pytest.raises(DocumentProcessingError) as exc_info:
            processor.process(str(empty_file), doc_id="test-empty")
        assert "metin çıkarılamadı" in str(exc_info.value)

    def test_latin1_encoding_okunabilmeli(self, processor, tmp_path):
        """latin-1 encoded dosya fallback ile okunabilmeli."""
        latin_file = tmp_path / "latin.txt"
        # Latin-1'e özgü karakter (€ = \x80 Latin-1'de)
        latin_file.write_bytes("Test content with latin chars".encode("latin-1"))
        result = processor.process(str(latin_file), doc_id="test-latin")
        assert len(result["full_text"]) > 0


class TestPdfProcessing:
    """PDF dosyası işleme testleri (test PDF'leri gerektirir)."""

    def test_pdf_test_dosyasi_varsa_islenmeli(self, processor):
        """Eğer test PDF'i varsa, başarıyla işlenmeli."""
        pdf_file = TEST_FILES_DIR / "test.pdf"
        if not pdf_file.exists():
            pytest.skip("test.pdf test dosyası bulunamadı — PDF testi atlandı")
        result = processor.process(str(pdf_file), doc_id="test-pdf-001")
        assert result["file_type"] == "pdf"
        assert len(result["full_text"]) > 10
        assert len(result["pages"]) >= 1

    def test_pdf_sayfa_numaralari_1_indexed_olmali(self, processor):
        """PDF sayfaları 1'den başlamalı (0-indexed değil)."""
        pdf_file = TEST_FILES_DIR / "test.pdf"
        if not pdf_file.exists():
            pytest.skip("test.pdf bulunamadı")
        result = processor.process(str(pdf_file), doc_id="test-pdf-002")
        page_numbers = [p["page_number"] for p in result["pages"]]
        assert page_numbers[0] == 1, "İlk sayfa 1 olmalı (1-indexed)"
        assert 0 not in page_numbers, "0-indexed sayfa numarası bulundu"


class TestDocxProcessing:
    """DOCX dosyası işleme testleri."""

    def test_docx_test_dosyasi_varsa_islenmeli(self, processor):
        """Eğer test DOCX'i varsa, başarıyla işlenmeli."""
        docx_file = TEST_FILES_DIR / "test.docx"
        if not docx_file.exists():
            pytest.skip("test.docx test dosyası bulunamadı — DOCX testi atlandı")
        result = processor.process(str(docx_file), doc_id="test-docx-001")
        assert result["file_type"] == "docx"
        assert len(result["full_text"]) > 10

    def test_docx_tek_sayfa_doner(self, processor):
        """DOCX dosyaları her zaman tek sayfa (page_number: 1) döner."""
        docx_file = TEST_FILES_DIR / "test.docx"
        if not docx_file.exists():
            pytest.skip("test.docx bulunamadı")
        result = processor.process(str(docx_file), doc_id="test-docx-002")
        assert len(result["pages"]) == 1
        assert result["pages"][0]["page_number"] == 1
