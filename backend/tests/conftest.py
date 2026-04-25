import pytest
from unittest.mock import AsyncMock


@pytest.fixture
def mock_cache():
    cache = AsyncMock()
    cache.get = AsyncMock(return_value=None)
    cache.set = AsyncMock()
    return cache


@pytest.fixture
def sample_doc_id():
    return "doc-test-001"
