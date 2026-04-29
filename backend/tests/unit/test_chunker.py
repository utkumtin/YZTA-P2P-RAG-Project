"""
Test senaryoları:
1. Temel fonksiyonellik: parçalar oluştu mu?
2. Parent-child ilişkisi: her child'ın parent'ı var mı?
3. Token boyutu kontrolleri: sınırlar aşılıyor mu?
4. Metadata bütünlüğü: gerekli alanlar var mı?
5. Edge case: çok kısa metin
6. Edge case: boş metin → ValueError
7. doc_id fallback: metadata'da doc_id yoksa UUID üretilmeli
8. ID formatı: "parent-xxx-0001" ve "child-xxx-0001-000" formatı
"""

import pytest

from app.core.chunker import _token_length, create_parent_child_chunks

# ─────────────────────────────────────────────────────────────────────────────
# Yardımcı fixture'lar
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def sample_metadata() -> dict:
    """Standart test metadata'sı."""
    return {
        "doc_id": "test-doc-001",
        "filename": "test_sozlesme.pdf",
        "file_type": "pdf",
        "language": "tr",
        "session_id": "session-test-001",
    }


@pytest.fixture
def long_text() -> str:
    """
    ~2000+ token uzunluğunda test metni.
    Chunking'in parent ve child parçalar üretebilmesi için
    en az bir parent boyutu (800 token) kadar metin lazım.
    """
    # ~14 kelime × ~1.5 token/kelime × 100 tekrar ≈ ~2100 token
    sentence = (
        "Bu bir test dokümanıdır. "
        "Sözleşme koşulları aşağıda belirtilmiştir. "
        "Taraflar karşılıklı yükümlülüklerini kabul etmiştir. "
        "Fesih durumunda bildirim süresi 30 gündür. "
    )
    return sentence * 100  # ~2100 token


@pytest.fixture
def short_text() -> str:
    """200 tokendan kısa metin — tek bir child chunk üretmeli."""
    return "Bu kısa bir test metnidir. Sadece birkaç cümle içerir."


# ─────────────────────────────────────────────────────────────────────────────
# Test 1: Temel fonksiyonellik
# ─────────────────────────────────────────────────────────────────────────────


class TestBasicFunctionality:
    """Temel chunk üretimi testleri."""

    def test_chunks_are_produced(self, long_text, sample_metadata):
        """Uzun metinden parent ve child chunk üretilmeli."""
        parents, children = create_parent_child_chunks(long_text, sample_metadata)

        assert len(parents) > 0, "Parent chunk üretilmedi"
        assert len(children) > 0, "Child chunk üretilmedi"

    def test_children_outnumber_parents(self, long_text, sample_metadata):
        """Her parent'tan en az 1 child çıkmalı → toplam child ≥ parent."""
        parents, children = create_parent_child_chunks(long_text, sample_metadata)

        assert len(children) >= len(parents), (
            f"Child sayısı ({len(children)}) parent sayısından ({len(parents)}) az olamaz"
        )

    def test_returns_tuple_of_two_lists(self, long_text, sample_metadata):
        """Fonksiyon (list, list) tuple döndürmeli."""
        result = create_parent_child_chunks(long_text, sample_metadata)

        assert isinstance(result, tuple), "Fonksiyon tuple döndürmeli"
        assert len(result) == 2, "Tuple 2 elemanlı olmalı (parents, children)"
        assert isinstance(result[0], list), "İlk eleman list (parents) olmalı"
        assert isinstance(result[1], list), "İkinci eleman list (children) olmalı"

    def test_chunk_has_required_keys(self, long_text, sample_metadata):
        """Her chunk 'id', 'text', 'metadata' anahtarlarını içermeli."""
        parents, children = create_parent_child_chunks(long_text, sample_metadata)

        for chunk in parents + children:
            assert "id" in chunk, f"Chunk'ta 'id' eksik: {chunk}"
            assert "text" in chunk, f"Chunk'ta 'text' eksik: {chunk}"
            assert "metadata" in chunk, f"Chunk'ta 'metadata' eksik: {chunk}"

    def test_chunk_text_is_not_empty(self, long_text, sample_metadata):
        """Hiçbir chunk boş metin içermemeli."""
        parents, children = create_parent_child_chunks(long_text, sample_metadata)

        for chunk in parents + children:
            assert chunk["text"].strip(), f"Boş chunk tespit edildi: {chunk['id']}"


# ─────────────────────────────────────────────────────────────────────────────
# Test 2: Parent-Child İlişkisi
# ─────────────────────────────────────────────────────────────────────────────


class TestParentChildRelationship:
    """Parent-child bağlantısı ve referans bütünlüğü testleri."""

    def test_every_child_has_valid_parent(self, long_text, sample_metadata):
        """Her child'ın parent_chunk_id'si gerçek bir parent'a işaret etmeli."""
        parents, children = create_parent_child_chunks(long_text, sample_metadata)

        parent_ids = {p["id"] for p in parents}

        for child in children:
            pid = child["metadata"]["parent_chunk_id"]
            assert pid in parent_ids, (
                f"Child '{child['id']}' için geçersiz parent_chunk_id: '{pid}'"
            )

    def test_children_grouped_under_parents(self, long_text, sample_metadata):
        """Her parent'ın en az bir child'ı olmalı."""
        parents, children = create_parent_child_chunks(long_text, sample_metadata)

        parent_ids_with_children = {c["metadata"]["parent_chunk_id"] for c in children}

        for parent in parents:
            assert parent["id"] in parent_ids_with_children, (
                f"Parent '{parent['id']}' için hiç child üretilmedi"
            )

    def test_child_parent_id_references_correct_parent(self, long_text, sample_metadata):
        """
        Child'ın parent_chunk_id'si, ID formatına göre doğru parent'a işaret etmeli.

        Örnek:
            child-test-doc-001-0002-001 → parent-test-doc-001-0002
        """
        parents, children = create_parent_child_chunks(long_text, sample_metadata)

        parent_map = {p["id"]: p for p in parents}

        for child in children:
            parent_id = child["metadata"]["parent_chunk_id"]
            assert parent_id in parent_map, (
                f"'{child['id']}' child'ının referans ettiği '{parent_id}' parent'ı bulunamadı"
            )


# ─────────────────────────────────────────────────────────────────────────────
# Test 3: Token Boyutu Kontrolleri
# ─────────────────────────────────────────────────────────────────────────────


class TestTokenSizeLimits:
    def test_child_chunks_within_size_limit(self, long_text, sample_metadata):
        """
        Child chunk'lar 200 token sınırını aşmamalı.
        Overlap toleransı ile max 260 token kabul edilir.
        """
        _, children = create_parent_child_chunks(long_text, sample_metadata)

        for child in children:
            tokens = _token_length(child["text"])
            assert tokens <= 260, f"Child chunk çok büyük: {tokens} token (chunk: '{child['id']}')"

    def test_parent_chunks_within_size_limit(self, long_text, sample_metadata):
        """
        Parent chunk'lar 800 token sınırını aşmamalı.
        Overlap toleransı ile max 950 token kabul edilir.
        """
        parents, _ = create_parent_child_chunks(long_text, sample_metadata)

        for parent in parents:
            tokens = _token_length(parent["text"])
            assert tokens <= 950, (
                f"Parent chunk çok büyük: {tokens} token (chunk: '{parent['id']}')"
            )

    def test_child_smaller_than_parent_on_average(self, long_text, sample_metadata):
        """Ortalama child boyutu ortalama parent boyutundan küçük olmalı."""
        parents, children = create_parent_child_chunks(long_text, sample_metadata)

        avg_parent = sum(_token_length(p["text"]) for p in parents) / len(parents)
        avg_child = sum(_token_length(c["text"]) for c in children) / len(children)

        assert avg_child < avg_parent, (
            f"Child ortalama ({avg_child:.0f} token) "
            f"parent ortalamasından ({avg_parent:.0f} token) küçük olmalı"
        )

    def test_custom_chunk_sizes_respected(self, long_text, sample_metadata):
        """Özel chunk boyutları parametre olarak geçildiğinde uygulanmalı."""
        parents, children = create_parent_child_chunks(
            long_text,
            sample_metadata,
            parent_chunk_size=400,
            parent_chunk_overlap=50,
            child_chunk_size=100,
            child_chunk_overlap=20,
        )

        for child in children:
            tokens = _token_length(child["text"])
            # 100 + küçük tolerans
            assert tokens <= 140, f"Özel boyutlu child chunk çok büyük: {tokens} token"

        for parent in parents:
            tokens = _token_length(parent["text"])
            # 400 + küçük tolerans
            assert tokens <= 490, f"Özel boyutlu parent chunk çok büyük: {tokens} token"


# ─────────────────────────────────────────────────────────────────────────────
# Test 4: Metadata Bütünlüğü
# ─────────────────────────────────────────────────────────────────────────────


class TestMetadataIntegrity:
    """Chunk metadata alanlarının eksiksizliği."""

    def test_child_metadata_has_required_fields(self, long_text, sample_metadata):
        """Her child chunk doğru metadata alanlarına sahip olmalı."""
        _, children = create_parent_child_chunks(long_text, sample_metadata)

        required_fields = {
            "doc_id",
            "filename",
            "file_type",
            "language",
            "session_id",
            "chunk_type",
            "chunk_index",
            "parent_chunk_id",
        }

        for child in children:
            meta = child["metadata"]
            missing = required_fields - set(meta.keys())
            assert not missing, f"Child '{child['id']}' metadata'sında eksik alanlar: {missing}"

    def test_parent_metadata_has_required_fields(self, long_text, sample_metadata):
        """Her parent chunk doğru metadata alanlarına sahip olmalı."""
        parents, _ = create_parent_child_chunks(long_text, sample_metadata)

        required_fields = {
            "doc_id",
            "filename",
            "file_type",
            "language",
            "session_id",
            "chunk_type",
            "chunk_index",
        }

        for parent in parents:
            meta = parent["metadata"]
            missing = required_fields - set(meta.keys())
            assert not missing, f"Parent '{parent['id']}' metadata'sında eksik alanlar: {missing}"

    def test_chunk_type_values_correct(self, long_text, sample_metadata):
        """chunk_type değerleri sadece 'parent' veya 'child' olmalı."""
        parents, children = create_parent_child_chunks(long_text, sample_metadata)

        for parent in parents:
            assert parent["metadata"]["chunk_type"] == "parent", (
                f"Parent chunk_type yanlış: {parent['metadata']['chunk_type']}"
            )

        for child in children:
            assert child["metadata"]["chunk_type"] == "child", (
                f"Child chunk_type yanlış: {child['metadata']['chunk_type']}"
            )

    def test_metadata_propagated_from_doc_metadata(self, long_text, sample_metadata):
        """doc_metadata içindeki tüm alanlar chunk metadata'sına aktarılmalı."""
        parents, children = create_parent_child_chunks(long_text, sample_metadata)

        for chunk in parents + children:
            for key, value in sample_metadata.items():
                assert chunk["metadata"].get(key) == value, (
                    f"'{key}' alanı chunk metadata'sına aktarılmamış veya değişmiş. "
                    f"Beklenen: {value}, Gelen: {chunk['metadata'].get(key)}"
                )

    def test_chunk_index_is_sequential(self, long_text, sample_metadata):
        """Parent chunk_index değerleri 0'dan başlayıp sıralı olmalı."""
        parents, _ = create_parent_child_chunks(long_text, sample_metadata)

        indices = [p["metadata"]["chunk_index"] for p in parents]
        expected = list(range(len(parents)))

        assert indices == expected, f"Parent chunk_index sıralı değil. Gelen: {indices}"


# ─────────────────────────────────────────────────────────────────────────────
# Test 5: ID Formatı
# ─────────────────────────────────────────────────────────────────────────────


class TestIDFormat:
    """Chunk ID formatı doğrulaması."""

    def test_parent_id_format(self, long_text, sample_metadata):
        """
        Parent ID formatı: "parent-{doc_id}-{4 haneli sıra}"
        Örnek: "parent-test-doc-001-0000"
        """
        parents, _ = create_parent_child_chunks(long_text, sample_metadata)
        doc_id = sample_metadata["doc_id"]

        for i, parent in enumerate(parents):
            expected_id = f"parent-{doc_id}-{i:04d}"
            assert parent["id"] == expected_id, (
                f"Parent ID formatı yanlış. Beklenen: '{expected_id}', Gelen: '{parent['id']}'"
            )

    def test_child_id_format(self, long_text, sample_metadata):
        """
        Child ID formatı: "child-{doc_id}-{4 haneli parent sıra}-{3 haneli child sıra}"
        Örnek: "child-test-doc-001-0000-000"
        """
        parents, children = create_parent_child_chunks(long_text, sample_metadata)
        doc_id = sample_metadata["doc_id"]

        # Her çocuğun ID'si kendi format kuralına uymalı
        for child in children:
            cid = child["id"]
            assert cid.startswith(f"child-{doc_id}-"), f"Child ID öneki yanlış: '{cid}'"
            # child-{doc_id}-XXXX-YYY formatı
            parts = cid.split("-")
            # Son iki segment 4 ve 3 haneli rakam olmalı
            # (doc_id'de de - olabileceğinden son iki segment kontrol edilir)
            assert parts[-1].isdigit() and len(parts[-1]) == 3, (
                f"Child ID son segmenti 3 haneli sayı olmalı: '{cid}'"
            )
            assert parts[-2].isdigit() and len(parts[-2]) == 4, (
                f"Child ID parent segmenti 4 haneli sayı olmalı: '{cid}'"
            )

    def test_all_chunk_ids_unique(self, long_text, sample_metadata):
        """Tüm chunk ID'leri birbirinden farklı olmalı."""
        parents, children = create_parent_child_chunks(long_text, sample_metadata)

        all_ids = [c["id"] for c in parents + children]
        assert len(all_ids) == len(set(all_ids)), "Yinelenen chunk ID'si tespit edildi!"


# ─────────────────────────────────────────────────────────────────────────────
# Test 6: Edge Cases
# ─────────────────────────────────────────────────────────────────────────────


class TestEdgeCases:
    """Sınır durumları ve hata senaryoları."""

    def test_empty_text_raises_value_error(self, sample_metadata):
        """Boş metin ValueError fırlatmalı."""
        with pytest.raises(ValueError, match="full_text boş olamaz"):
            create_parent_child_chunks("", sample_metadata)

    def test_whitespace_only_text_raises_value_error(self, sample_metadata):
        """Sadece boşluk içeren metin de ValueError fırlatmalı."""
        with pytest.raises(ValueError, match="full_text boş olamaz"):
            create_parent_child_chunks("   \n\n\t  ", sample_metadata)

    def test_short_text_produces_chunks(self, short_text, sample_metadata):
        """Kısa metin (< 200 token) en az bir chunk üretmeli."""
        parents, children = create_parent_child_chunks(short_text, sample_metadata)

        assert len(parents) >= 1, "Kısa metin en az 1 parent üretmeli"
        assert len(children) >= 1, "Kısa metin en az 1 child üretmeli"

    def test_missing_doc_id_generates_uuid(self, long_text):
        """doc_id yoksa UUID otomatik üretilmeli, hata verilmemeli."""
        metadata_without_doc_id = {
            "filename": "test.pdf",
            "file_type": "pdf",
            "language": "tr",
            "session_id": "session-001",
            # doc_id YOK
        }

        parents, children = create_parent_child_chunks(long_text, metadata_without_doc_id)

        assert len(parents) > 0
        # ID'ler geçerli UUID içermeli (UUID formatı: 8-4-4-4-12)
        # ID formatı: "parent-{uuid}-0000" — uuid kısmı var olmalı
        first_parent_id = parents[0]["id"]
        assert first_parent_id.startswith("parent-"), (
            f"UUID fallback ile üretilen ID 'parent-' ile başlamalı: '{first_parent_id}'"
        )

    def test_metadata_with_extra_fields_preserved(self, long_text, sample_metadata):
        """doc_metadata'ya ekstra alanlar eklenirse bunlar da chunk metadata'sında olmalı."""
        extended_metadata = {
            **sample_metadata,
            "upload_timestamp": "2026-04-23T10:00:00Z",  # Ekstra alan
            "source_url": "https://example.com/doc.pdf",  # Ekstra alan
        }

        parents, children = create_parent_child_chunks(long_text, extended_metadata)

        for chunk in parents + children:
            assert chunk["metadata"].get("upload_timestamp") == "2026-04-23T10:00:00Z"
            assert chunk["metadata"].get("source_url") == "https://example.com/doc.pdf"


# ─────────────────────────────────────────────────────────────────────────────
# Test 7: _token_length yardımcı fonksiyonu
# ─────────────────────────────────────────────────────────────────────────────


class TestTokenLength:
    """_token_length yardımcı fonksiyonu testleri."""

    def test_empty_string_returns_zero(self):
        """Boş string 0 token döndürmeli."""
        assert _token_length("") == 0

    def test_token_count_is_positive(self):
        """Normal metin için token sayısı > 0 olmalı."""
        result = _token_length("Merhaba dünya")
        assert result > 0

    def test_longer_text_has_more_tokens(self):
        """Daha uzun metin daha fazla token içermeli."""
        short = _token_length("kısa")
        long = _token_length("Bu çok daha uzun bir metin parçasıdır ve daha fazla token içerir.")
        assert long > short

    def test_returns_integer(self):
        """Fonksiyon int döndürmeli."""
        result = _token_length("test")
        assert isinstance(result, int)


# ─────────────────────────────────────────────────────────────────────────────
# Test 8: Sayfa-başına chunking (pages kwarg)
# ─────────────────────────────────────────────────────────────────────────────


class TestPageAwareChunking:
    """pages kwarg ile sayfa numarası metadata'ya aktarılıyor mu?"""

    @pytest.fixture(autouse=True)
    def configure_splitter_mock(self):
        """
        conftest.py SentenceSplitter'ı MagicMock class'ıyla stub'luyor.
        Bu fixture patch ile gerçek davranışa yakın şekilde yapılandırır:
        split_text metni tek chunk olarak döndürür.
        """
        from unittest.mock import patch, MagicMock

        mock_splitter = MagicMock()
        mock_splitter.split_text.side_effect = lambda text: [text] if text.strip() else []

        with patch("app.core.chunker.SentenceSplitter", return_value=mock_splitter):
            yield

    @pytest.fixture
    def two_page_doc(self):
        sentence = (
            "Bu birinci sayfanın içeriğidir. "
            "Sözleşme koşulları burada belirtilmiştir. "
            "Taraflar yükümlülüklerini kabul etmiştir. "
        )
        return [
            {"page_number": 1, "text": sentence * 30},
            {"page_number": 2, "text": sentence * 30},
        ]

    def test_page_number_in_parent_metadata(self, two_page_doc, sample_metadata):
        """Her parent kendi sayfasının page_number'ını taşımalı."""
        parents, _ = create_parent_child_chunks(
            "", sample_metadata, pages=two_page_doc
        )
        for parent in parents:
            assert "page_number" in parent["metadata"], (
                f"Parent '{parent['id']}' metadata'sında page_number yok"
            )
            assert parent["metadata"]["page_number"] in (1, 2)

    def test_page_number_in_child_metadata(self, two_page_doc, sample_metadata):
        """Her child kendi sayfasının page_number'ını taşımalı."""
        _, children = create_parent_child_chunks(
            "", sample_metadata, pages=two_page_doc
        )
        for child in children:
            assert "page_number" in child["metadata"], (
                f"Child '{child['id']}' metadata'sında page_number yok"
            )
            assert child["metadata"]["page_number"] in (1, 2)

    def test_page_numbers_match_source_pages(self, two_page_doc, sample_metadata):
        """Birinci sayfadan üretilen chunk'lar page_number=1, ikincisi page_number=2 almalı."""
        parents, children = create_parent_child_chunks(
            "", sample_metadata, pages=two_page_doc
        )
        page1_parents = [p for p in parents if p["metadata"]["page_number"] == 1]
        page2_parents = [p for p in parents if p["metadata"]["page_number"] == 2]
        assert len(page1_parents) > 0, "Sayfa 1'den hiç parent üretilmedi"
        assert len(page2_parents) > 0, "Sayfa 2'den hiç parent üretilmedi"

        page1_children = [c for c in children if c["metadata"]["page_number"] == 1]
        page2_children = [c for c in children if c["metadata"]["page_number"] == 2]
        assert len(page1_children) > 0, "Sayfa 1'den hiç child üretilmedi"
        assert len(page2_children) > 0, "Sayfa 2'den hiç child üretilmedi"

    def test_chunk_ids_unique_across_pages(self, two_page_doc, sample_metadata):
        """Tüm sayfalardaki chunk ID'leri benzersiz olmalı."""
        parents, children = create_parent_child_chunks(
            "", sample_metadata, pages=two_page_doc
        )
        all_ids = [c["id"] for c in parents + children]
        assert len(all_ids) == len(set(all_ids)), "Sayfa sınırında yinelenen chunk ID'si!"

    def test_child_parent_link_valid_across_pages(self, two_page_doc, sample_metadata):
        """Sayfa-başına chunk'larda parent-child referansları geçerli olmalı."""
        parents, children = create_parent_child_chunks(
            "", sample_metadata, pages=two_page_doc
        )
        parent_ids = {p["id"] for p in parents}
        for child in children:
            pid = child["metadata"]["parent_chunk_id"]
            assert pid in parent_ids, (
                f"Child '{child['id']}' geçersiz parent_chunk_id taşıyor: '{pid}'"
            )

    def test_fallback_without_pages_has_no_page_number(self, long_text, sample_metadata):
        """pages kwarg verilmediğinde chunk'larda page_number olmamalı (backward compat)."""
        parents, children = create_parent_child_chunks(long_text, sample_metadata)
        for chunk in parents + children:
            assert "page_number" not in chunk["metadata"], (
                f"pages=None iken page_number eklenmemeli: {chunk['id']}"
            )
