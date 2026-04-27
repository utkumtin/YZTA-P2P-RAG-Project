"""
Doküman işleme modülü.
PDF, DOCX, DOC ve TXT dosyalarından metin çıkarır.
Taranmış PDF'lerde Surya OCR devreye girer.

Bu modül şu akışı yönetir:
1. Dosya formatını tespit et (uzantıdan)
2. Uygun parser'a yönlendir
3. Her sayfa için metin çıkar
4. Taranmış sayfaları OCR'a gönder
5. Tüm metni birleştir ve döndür
"""

import os
from pathlib import Path

import fitz  # PyMuPDF — PDF okuma kütüphanesi
from docx import Document  # python-docx — DOCX okuma kütüphanesi

from app.core.text_cleaner import clean_text


class DocumentProcessingError(Exception):
    """
    Doküman işleme sırasında oluşan hatalar için özel exception.

    Kullanım yerleri:
    - Dosya bulunamadığında
    - Desteklenmeyen format
    - Dosyadan metin çıkarılamadığında
    - OCR başarısız olduğunda
    """

    pass


class DocumentProcessor:
    """
    Tüm dosya formatlarını işleyen ana sınıf.
    Her format için ayrı bir private metod var.

    ÖNEMLİ TASARIM KARARLARI:

    1. Surya OCR modelleri LAZY-LOAD edilir.

    2. OCR eşik değeri: 50 karakter.

    3. OCR DPI: 300.

    Kullanım:
        processor = DocumentProcessor()
        result = processor.process("/path/to/file.pdf", doc_id="uuid-...")
    """

    # Surya OCR modelleri — class-level değişkenler
    # None ile başlatılır, ilk OCR çağrısında yüklenir
    _surya_det_model = None  # Detection (yazı alanı tespit) modeli
    _surya_rec_model = None  # Recognition (karakter tanıma) modeli

    # Taranmış sayfa tespit eşiği
    OCR_CHAR_THRESHOLD = 50

    # OCR render kalitesi (DPI = dots per inch)
    OCR_DPI = 300

    def process(self, file_path: str, doc_id: str = None) -> dict:
        """
        Ana giriş noktası. Verilen dosyayı formatına göre işler.

        Args:
            file_path: Diskteki dosya yolu (örn: "/app/uploads/abc123.pdf")
            doc_id: Doküman UUID'si.

        Returns:
            dict: {
                "doc_id": str veya None,
                "filename": str,        # Orijinal dosya adı
                "file_type": str,       # "pdf", "docx", "doc", "txt"
                "pages": list[dict],    # [{"page_number": int, "text": str}, ...]
                "full_text": str,       # Tüm sayfa metinleri birleşik (temizlenmiş)
                "language": str         # "tr", "en", "unknown"
            }

        Raises:
            DocumentProcessingError: Dosya bulunamadı, format desteklenmiyor, veya metin çıkarılamadı.
        """
        # Dosya var mı kontrol et
        if not os.path.exists(file_path):
            raise DocumentProcessingError(f"Dosya bulunamadı: {file_path}")

        # Uzantıyı al ve normalize et
        ext = Path(file_path).suffix.lower().lstrip(".")
        filename = Path(file_path).name

        # Format'a göre uygun parser'ı seç
        # Python 3.10+ match-case kullanıyoruz
        match ext:
            case "pdf":
                pages = self._process_pdf(file_path)
            case "docx":
                pages = self._process_docx(file_path)
            case "doc":
                pages = self._process_doc(file_path)
            case "txt":
                pages = self._process_txt(file_path)
            case _:
                raise DocumentProcessingError(
                    f"Desteklenmeyen dosya formatı: .{ext}. "
                    "Desteklenen formatlar: PDF, DOCX, DOC, TXT"
                )

        # Sayfa-başına temizle — chunker page_number eşlemesi için buna ihtiyaç duyuyor
        cleaned_pages = []
        for p in pages:
            if not p["text"].strip():
                continue
            cleaned, _ = clean_text(p["text"])
            if cleaned.strip():
                cleaned_pages.append({"page_number": p["page_number"], "text": cleaned})

        # Dosyadan hiç metin çıkamadıysa hata ver
        if not cleaned_pages:
            raise DocumentProcessingError(
                f"Dosyadan metin çıkarılamadı: {filename}. "
                "Dosya boş olabilir veya içerik okunamaz formatta olabilir."
            )

        full_text = "\n\n".join(p["text"] for p in cleaned_pages)

        # Dil tespiti birleşik metin üzerinden yapılır (daha güvenilir)
        _, language = clean_text(full_text)

        return {
            "doc_id": doc_id,
            "filename": filename,
            "file_type": ext,
            "pages": cleaned_pages,
            "full_text": full_text,
            "language": language,
        }

    """
    PDF İŞLEME
    """

    def _process_pdf(self, file_path: str) -> list[dict]:
        """
        PDF dosyasını işler. Her sayfa için metin çıkarır.
        Taranmış sayfalar tespit edildiğinde Surya OCR devreye girer.

        Akış:
        1. PyMuPDF ile PDF'i aç
        2. Her sayfa için page.get_text("text") çağır
        3. Çıkan metin < 50 karakter ise → taranmış sayfa, OCR'a gönder
        4. Sonucu [{page_number, text}, ...] olarak döndür

        Returns:
            list[dict]: Her sayfa için {"page_number": int, "text": str}
        """
        try:
            doc = fitz.open(file_path)
        except Exception as e:
            raise DocumentProcessingError(f"PDF açılamadı: {e}")

        pages = []

        for page_num in range(len(doc)):
            page = doc[page_num]

            # PyMuPDF ile metin katmanından çıkar
            # "text" modu: düz metin, layout bilgisi olmadan
            text = page.get_text("text")

            # Taranmış sayfa tespiti
            # Dijital PDF: binlerce karakter olur
            # Taranmış PDF: 0 veya birkaç karakter (sayfa no, header)
            if len(text.strip()) < self.OCR_CHAR_THRESHOLD:
                text = self._ocr_page(page, page_num)

            pages.append(
                {
                    "page_number": page_num + 1,  # 1-indexed (kullanıcıya gösterilecek)
                    "text": text,
                }
            )

        doc.close()
        return pages

    def _ocr_page(self, page, page_num: int) -> str:
        """
        Taranmış bir PDF sayfasını Surya OCR ile okur.

        Args:
            page: PyMuPDF sayfa nesnesi
            page_num: 0-indexed sayfa numarası (log mesajları için)

        Returns:
            str: OCR ile okunan metin. Başarısız olursa boş string.
        """
        # Lazy-load: OCR modelleri sadece ilk çağrıda yüklenir
        if DocumentProcessor._surya_det_model is None:
            from surya.model.detection import segformer
            from surya.model.recognition import recognition

            DocumentProcessor._surya_det_model = segformer.load_model()
            DocumentProcessor._surya_rec_model = recognition.load_model()

        from surya.ocr import run_ocr

        # Sayfayı 300 DPI'da görsel olarak renderla
        pix = page.get_pixmap(dpi=self.OCR_DPI)
        image = pix.tobytes("png")

        try:
            result = run_ocr(
                images=[image],
                langs=["tr", "en"],  # Türkçe öncelikli, İngilizce yedek
                det_model=DocumentProcessor._surya_det_model,
                rec_model=DocumentProcessor._surya_rec_model,
            )

            # Surya sonuçlarını okuma sırasına göre birleştir
            # Surya metin satırlarını zaten doğru sırada döndürür
            text_blocks = [line.text for line in result[0].text_lines]
            return "\n".join(text_blocks)

        except Exception as e:
            # OCR başarısız olursa boş string döndür
            # Bu sayfanın metni kayıp ama diğer sayfalar işlenmeye devam eder
            # Crash ettirmiyoruz çünkü 50 sayfalık PDF'de 1 sayfa bozuk olabilir
            print(f"UYARI: Sayfa {page_num + 1} için OCR başarısız: {e}")
            return ""

    """
    DOCX İŞLEME
    """

    def _process_docx(self, file_path: str) -> list[dict]:
        """
        DOCX dosyasını parse eder.
        Paragraflar, başlıklar ve tablolar (nested dahil) belge sırasıyla çıkarılır.

        Başlık hiyerarşisi Markdown formatında korunur.
        Tablolar düz metne dönüştürülür (hücreler " | " ile ayrılır).
        Nested tablolar recursive olarak işlenir — üst düzey doc.tables atlar bunları.
        """
        try:
            doc = Document(file_path)
        except Exception as e:
            raise DocumentProcessingError(f"DOCX açılamadı: {e}")

        from docx.oxml.ns import qn

        def extract_table_text(tbl_element) -> str:
            """Nested tablolar dahil tüm tablo içeriğini çıkarır."""
            rows = []
            for tr in tbl_element.findall(f".//{qn('w:tr')}"):
                cells = []
                for tc in tr.findall(f".//{qn('w:tc')}"):
                    # Hücre içindeki tüm metni al (nested table'lar dahil)
                    texts = []
                    for p in tc.findall(f".//{qn('w:p')}"):
                        t = "".join(r.text or "" for r in p.findall(f".//{qn('w:t')}"))
                        if t.strip():
                            texts.append(t.strip())
                    cells.append(" ".join(texts))
                row_text = " | ".join(c for c in cells if c)
                if row_text.strip():
                    rows.append(row_text)
            return "\n".join(rows)

        content_blocks = []

        # Belge gövdesindeki üst düzey elementleri sırayla işle
        body = doc.element.body
        for child in body:
            tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag

            if tag == "p":
                # Paragraf
                from docx.text.paragraph import Paragraph
                para = Paragraph(child, doc)
                if para.style.name.startswith("Heading") and para.text.strip():
                    level_str = para.style.name.replace("Heading ", "").strip()
                    level = int(level_str) if level_str.isdigit() else 1
                    content_blocks.append(f"{'#' * level} {para.text}")
                elif para.text.strip():
                    content_blocks.append(para.text)

            elif tag == "tbl":
                # Üst düzey tablo (nested tablolar bu çağrı içinde recursive işlenir)
                table_text = extract_table_text(child)
                if table_text.strip():
                    content_blocks.append(table_text)

        full_text = "\n\n".join(content_blocks)

        return [{"page_number": 1, "text": full_text}]

    """
    DOC İŞLEME (Eski İkili Format)
    """

    def _process_doc(self, file_path: str) -> list[dict]:
        """
        Eski .doc dosyalarını saf Python ile okur.

        Fallback zinciri:
        1. sharepoint-to-text ile oku
        2. Başarısız olursa → kullanıcıya DOCX'e dönüştürme öner
        """
        try:
            from sharepointtotext import DocReader

            reader = DocReader(file_path)
            text = reader.extract_text()

            if not text or not text.strip():
                raise DocumentProcessingError(
                    ".doc dosyasından metin çıkarılamadı. "
                    "Lütfen dosyayı DOCX formatına dönüştürüp tekrar yükleyin."
                )

            return [{"page_number": 1, "text": text}]

        except ImportError:
            raise DocumentProcessingError(
                ".doc format desteği için sharepoint-to-text kurulu değil. "
                "Lütfen dosyayı DOCX formatına dönüştürüp tekrar yükleyin."
            )
        except DocumentProcessingError:
            raise  # Kendi hatamızı tekrar fırlat (yukarıdaki catch'e düşmesin)
        except Exception as e:
            raise DocumentProcessingError(
                f".doc dosyası okunamadı: {e}. "
                "Lütfen dosyayı Microsoft Word veya LibreOffice ile "
                "DOCX formatına dönüştürüp tekrar yükleyin."
            )

    """
    TXT İŞLEME
    """

    def _process_txt(self, file_path: str) -> list[dict]:
        """
        TXT dosyasını kademeli encoding fallback ile okur.

        Fallback sırası (en yaygından en az yaygına):
        1. UTF-8 strict   → Modern dosyaların %90'ı
        2. cp1254 strict   → Eski Türkçe dosyalar
        3. chardet analiz   → Nadir durumlar
        4. latin-1          → Son çare (asla hata vermez ama bozulabilir)
        """
        # 1. UTF-8 strict — En yaygın modern encoding
        try:
            with open(file_path, encoding="utf-8", errors="strict") as f:
                text = f.read()
                return [{"page_number": 1, "text": text}]
        except UnicodeDecodeError:
            pass  # UTF-8 değilmiş, devam et

        # 2. Windows-1254 — Türkçe için en yaygın legacy encoding
        try:
            with open(file_path, encoding="cp1254", errors="strict") as f:
                text = f.read()
                return [{"page_number": 1, "text": text}]
        except UnicodeDecodeError:
            pass  # cp1254 de değilmiş, devam et

        # 3. chardet ile otomatik tespit
        try:
            import chardet

            with open(file_path, "rb") as f:
                raw = f.read()
            detected = chardet.detect(raw)
            encoding = detected.get("encoding", "latin-1")
            text = raw.decode(encoding, errors="replace")
            return [{"page_number": 1, "text": text}]
        except Exception:
            pass

        # 4. Son çare: latin-1 — asla UnicodeDecodeError vermez
        # ama Türkçe karakterler bozulabilir
        with open(file_path, encoding="latin-1") as f:
            text = f.read()
            return [{"page_number": 1, "text": text}]
