from tokenish_engine.mib import TokenishBinaryIndex, rank_chunks_binary, texts_to_binary_matrix


def test_binary_matrix_shape():
    mat = texts_to_binary_matrix(["alpha revenue audit", "beta cake recipe", "gamma ledger"], bits=512)
    assert mat.shape == (3, 64)
    assert mat.dtype.name == "uint8"


def test_faiss_or_numpy_search_returns_hits():
    chunks = [
        "quarterly revenue growth financial audit ledger",
        "chocolate cake flour sugar butter recipe",
        "balance sheet assets liabilities equity",
        "pasta tomato basil olive oil dinner",
        "earnings per share and operating margin",
    ] * 3
    ranked = rank_chunks_binary("financial revenue audit", chunks, bits=512, top_k=5)
    assert len(ranked) >= 1
    assert ranked[0][0] >= 0
    # Financial-ish chunks should rank ahead of food on average for top hit text
    assert "financial" in ranked[0][2].lower() or "revenue" in ranked[0][2].lower() or "earnings" in ranked[0][2].lower()


def test_index_backend_reports():
    idx = TokenishBinaryIndex(bits=512)
    idx.add_texts(["one", "two", "three"])
    assert idx.backend in {"faiss", "numpy"}
    hits = idx.search_text("one", k=2)
    assert len(hits) >= 1
