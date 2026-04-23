"""
Metin temizleme modülü.
Ham metinden embedding-dostu temiz metin üretir.
"""

import re

from langdetect import LangDetectException, detect


def clean_text(raw_text: str) -> tuple[str, str]:
    """
    Ham metni temizler ve dil tespiti yapar.

    Args:
        raw_text: Doküman parser'ından gelen ham metin

    Returns:
        tuple: (temiz_metin, dil_kodu)

        dil_kodu örnekleri:
        - "tr" = Türkçe
        - "en" = İngilizce
        - "de" = Almanca
        - "unknown" = tespit edilemedi
    """
    text = raw_text

    # ---- ADIM 1: Kontrol karakterlerini kaldır ----
    # Kaldırılanlar: \x00-\x08 (NULL, SOH, STX...), \x0b (Vertical Tab),
    #                \x0c (Form Feed), \x0e-\x1f (Shift Out → Unit Separator)
    # KORUNANLAR: \t (tab, \x09) ve \n (newline, \x0a)
    # Neden korunuyor: Tab ve yeni satır anlamsal yapıyı korur
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)

    # ---- ADIM 2: Çoklu boşluk ve tab'ları tekleştir ----
    # "Merhaba     dünya" → "Merhaba dünya"
    # Tab'lar da boşluğa dönüşür (satır içi tab anlamsız)
    text = re.sub(r"[ \t]+", " ", text)

    # ---- ADIM 3: 3+ ardışık boş satırı çift satır sonuna indirge ----
    # Paragraf ayırıcı olarak \n\n yeterli
    # 3+ boş satır genelde format bozukluğu (PDF'den gelen)
    text = re.sub(r"\n{3,}", "\n\n", text)

    # ---- ADIM 4: Dekoratif karakter tekrarlarını normalize et ----
    # PDF ve Word'de bölüm ayırıcı olarak kullanılır
    # "==================" → "==="
    text = re.sub(r"[-]{4,}", "---", text)
    text = re.sub(r"[*]{4,}", "***", text)
    text = re.sub(r"[=]{4,}", "===", text)
    text = re.sub(r"[_]{4,}", "___", text)

    # ---- ADIM 5: Sayfa numarası kalıplarını kaldır ----
    # Bu kalıplar her sayfada tekrarlanır ve embedding'i kirletir

    # Türkçe kalıplar
    text = re.sub(r"Sayfa\s+\d+\s*/\s*\d+", "", text)  # "Sayfa 7 / 42"
    text = re.sub(r"Sayfa\s+\d+", "", text)  # "Sayfa 7"

    # İngilizce kalıplar
    text = re.sub(r"Page\s+\d+\s+of\s+\d+", "", text, flags=re.IGNORECASE)  # "Page 7 of 42"
    text = re.sub(r"Page\s+\d+", "", text, flags=re.IGNORECASE)  # "Page 7"

    # Tek başına sayfa numarası (satır başında/sonunda tek sayı)
    # Dikkat: Bu agresif bir regex. 4 haneye kadar sınırlandırdık
    # çünkü 5+ haneli tek başına sayı normal metin olabilir.
    text = re.sub(r"^\s*\d{1,4}\s*$", "", text, flags=re.MULTILINE)

    # ---- ADIM 6: Satır başı/sonu boşluklarını temizle ----
    lines = [line.strip() for line in text.split("\n")]
    text = "\n".join(lines)

    # ---- ADIM 7: Baştaki/sondaki boşluk ----
    text = text.strip()

    # ---- ADIM 8: Dil tespiti ----
    lang = _detect_language(text)

    return text, lang


def _detect_language(text: str) -> str:
    """
    Metnin dilini tespit eder.

    langdetect kütüphanesi kullanılır.
    İlk 1000 karakter yeterli — daha fazlası gereksiz CPU harcar.

    Args:
        text: Temizlenmiş metin

    Returns:
        str: ISO 639-1 dil kodu ("tr", "en", vb.) veya "unknown"
    """
    try:
        sample = text[:1000]
        # Çok kısa metinlerde dil tespiti güvenilmez
        if len(sample.strip()) < 20:
            return "unknown"
        return detect(sample)
    except LangDetectException:
        return "unknown"
