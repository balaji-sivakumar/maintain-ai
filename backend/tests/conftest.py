import shutil

import pytest
from dotenv import load_dotenv

from impl.local_storage import DEFAULT_REFERENCE_PATH, LocalJsonStorage

load_dotenv()  # makes DATABASE_URL/OPENAI_API_KEY visible to skipif-guarded live tests


@pytest.fixture
def isolated_storage(tmp_path):
    """LocalJsonStorage backed by its own copy of the reference table.

    Use this (instead of constructing LocalJsonStorage directly) in any test
    that calls cache_reference_data() — that method writes to the reference
    file, and without this, tests silently reformat/pollute the real
    backend/data/appliances.json.
    """
    reference_path = tmp_path / "appliances.json"
    shutil.copy(DEFAULT_REFERENCE_PATH, reference_path)
    return LocalJsonStorage(reference_path=reference_path, state_path=tmp_path / "local_state.json")
