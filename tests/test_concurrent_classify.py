"""验证并发分类线程安全：并发结果应与串行一致。"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pytest

from classify import Classifier


@pytest.fixture
def clf(categories_path):
    return Classifier(categories_path, llm=None)


def _make_files(d: Path, n: int):
    names = ["起诉状", "答辩状", "委托合同", "发票", "判决书", "代理词", "证据目录", "随机xyz"]
    paths = []
    for i in range(n):
        nm = names[i % len(names)]
        p = d / f"{nm}_{i}.pdf"
        p.write_text("x", encoding="utf-8")
        paths.append(p)
    return paths


def test_concurrent_matches_sequential(clf, tmp_case_dir):
    files = _make_files(tmp_case_dir, 24)

    # 串行基线
    seq = {f.name: clf.classify(f, role="原告").category_id for f in files}

    # 并发（与 ClassifyWorker 同样模式）
    results = {}
    with ThreadPoolExecutor(max_workers=5) as pool:
        futs = {pool.submit(clf.classify, f, "原告"): f for f in files}
        for fut in as_completed(futs):
            f = futs[fut]
            results[f.name] = fut.result().category_id

    assert results == seq, "并发分类结果与串行不一致（线程安全问题）"


def test_concurrent_order_preserved(clf, tmp_case_dir):
    files = _make_files(tmp_case_dir, 12)
    total = len(files)
    out = [None] * total

    def work(i, fp):
        return i, clf.classify(fp, role="原告")

    with ThreadPoolExecutor(max_workers=4) as pool:
        futs = [pool.submit(work, i, f) for i, f in enumerate(files)]
        for fut in as_completed(futs):
            idx, c = fut.result()
            out[idx] = c

    # 所有槽位都被填充，顺序与输入一致
    assert all(c is not None for c in out)
    assert [c.file_path.name for c in out] == [f.name for f in files]
