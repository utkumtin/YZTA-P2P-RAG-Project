"""
pytest ile çalıştır:
    cd backend
    pytest tests/unit/test_text_cleaner.py -v
"""

from app.core.text_cleaner import clean_text


class TestCleanText:
    """clean_text() fonksiyonu için birim testler."""

    def test_kontrol_karakterleri_temizlenmeli(self):
        """\\x00, \\x0c gibi kontrol karakterleri kaldırılmalı, \\n korunmalı."""
        dirty = "Merhaba\x00 dünya\x0c test\x1f sonu"
        clean, lang = clean_text(dirty)
        assert "\x00" not in clean, "\\x00 temizlenmedi"
        assert "\x0c" not in clean, "\\x0c temizlenmedi"
        assert "\x1f" not in clean, "\\x1f temizlenmedi"
        assert "Merhaba" in clean, "Normal metin kayboldu"
        assert "dünya" in clean, "Normal metin kayboldu"

    def test_newline_korunmali(self):
        """\\n karakteri anlamsal yapı için korunmalı."""
        text = "Birinci satır\nİkinci satır"
        clean, _ = clean_text(text)
        assert "\n" in clean, "\\n korunmadı"

    def test_coklu_bosluk_teklesmeli(self):
        """Ardışık boşluklar tek boşluğa indirgenmeli."""
        dirty = "Merhaba     dünya   test"
        clean, _ = clean_text(dirty)
        assert "  " not in clean, "Çoklu boşluk tekleştirilmedi"
        assert "Merhaba dünya test" in clean

    def test_uc_ten_fazla_bos_satir_indirgenmeli(self):
        """3+ ardışık boş satır → çift satır sonu."""
        dirty = "Birinci\n\n\n\n\n\nİkinci"
        clean, _ = clean_text(dirty)
        assert "\n\n\n" not in clean, "3+ boş satır temizlenmedi"
        assert "Birinci" in clean
        assert "İkinci" in clean

    def test_dekoratif_ayiricilar_normalize_edilmeli(self):
        """----, ****, ====, ____ → ---, ***, ===, ___"""
        dirty = "Başlık\n===================\nİçerik\n--------------------\nAlt"
        clean, _ = clean_text(dirty)
        assert "====================" not in clean
        assert "==" not in clean.replace("===", "")  # sadece === kalmalı
        assert "--------------------" not in clean

    def test_turkce_sayfa_numarasi_kaldirilmali(self):
        """'Sayfa 7 / 42' ve 'Sayfa 7' kalıpları kaldırılmalı."""
        dirty = "Önemli bilgi\nSayfa 7 / 42\nDevam ediyor"
        clean, _ = clean_text(dirty)
        assert "Sayfa 7" not in clean, "Sayfa numarası kaldırılmadı"
        assert "Önemli bilgi" in clean

    def test_ingilizce_sayfa_numarasi_kaldirilmali(self):
        """'Page 7 of 42' kalıbı kaldırılmalı."""
        dirty = "Important info\nPage 7 of 42\nContinues here"
        clean, _ = clean_text(dirty)
        assert "Page 7" not in clean, "Page numarası kaldırılmadı"
        assert "Important info" in clean

    def test_idempotent(self):
        """Aynı metni iki kez temizlemek aynı sonucu vermeli."""
        text = "Merhaba\x00 dünya\n\n\n\ntest   metin   Sayfa 5"
        clean1, lang1 = clean_text(text)
        clean2, lang2 = clean_text(clean1)
        assert clean1 == clean2, "Fonksiyon idempotent değil"
        assert lang1 == lang2

    def test_bos_metin_islenmeli(self):
        """Boş metin hata vermemeli, boş string ve 'unknown' döndürmeli."""
        clean, lang = clean_text("")
        assert clean == ""
        assert lang == "unknown"

    def test_cok_kisa_metin_unknown_dil(self):
        """20 karakterden kısa metin için dil 'unknown' dönmeli."""
        clean, lang = clean_text("Kısa")
        assert lang == "unknown"


class TestDetectLanguage:
    """_detect_language() fonksiyonu için birim testler."""

    def test_turkce_tespit(self):
        """Türkçe metin 'tr' olarak tespit edilmeli."""
        _, lang = clean_text(
            "Bu bir Türkçe metindir. Sözleşme koşulları aşağıda belirtilmiştir. "
            "Taraflar arasında mutabakat sağlanmıştır. Ödeme planı şu şekildedir."
        )
        assert lang == "tr", f"Beklenen 'tr', gelen '{lang}'"

    def test_ingilizce_tespit(self):
        """İngilizce metin 'en' olarak tespit edilmeli."""
        _, lang = clean_text(
            "This is an English document. The contract terms are listed below. "
            "The parties have reached an agreement on the payment schedule."
        )
        assert lang == "en", f"Beklenen 'en', gelen '{lang}'"
