"""Tests for the creative primitives (Phase 1)."""

import sys
import time
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from directo.creative import (
    GalleryView,
    GenerationStrategy,
    ImageHistory,
    Reference,
    ReferenceKind,
    ReferenceLibrary,
    Variant,
    VariantLock,
    VariantSet,
    VariantStore,
    ViewLayout,
)
from directo.creative.variants import plan_seeds
from directo.gallery import Gallery, ImageRecord
from directo.creative.references import PillowBackend


# ============================================================
# Variants
# ============================================================


def test_variant_set_lock_idempotent():
    vs = VariantSet(
        id="vs1", decision_key="scene_01",
        prompt_template="a dragon",
        variants=[Variant(index=0, image_id="img1"), Variant(index=1, image_id="img2")],
    )
    vs.lock_variant(0)
    vs.lock_variant(0)  # idempotent
    assert vs.lock == VariantLock.LOCKED
    assert vs.locked_index == 0
    assert vs.locked_variant().image_id == "img1"


def test_variant_set_lock_out_of_range():
    vs = VariantSet(id="vs", decision_key="k", prompt_template="p", variants=[])
    with pytest.raises(ValueError):
        vs.lock_variant(0)


def test_variant_set_lock_empty_image_raises():
    vs = VariantSet(
        id="vs", decision_key="k", prompt_template="p",
        variants=[Variant(index=0, image_id=None)],
    )
    with pytest.raises(ValueError):
        vs.lock_variant(0)


def test_variant_set_unlock():
    vs = VariantSet(
        id="vs", decision_key="k", prompt_template="p",
        variants=[Variant(index=0, image_id="img1")],
    )
    vs.lock_variant(0)
    vs.unlock()
    assert vs.lock == VariantLock.OPEN
    assert vs.locked_variant() is None


def test_variant_set_reject():
    vs = VariantSet(
        id="vs", decision_key="k", prompt_template="p",
        variants=[Variant(index=0, image_id="img1")],
    )
    vs.reject_all()
    assert vs.lock == VariantLock.REJECTED


def test_variant_set_round_trip_db():
    with VariantStore(":memory:") as s:
        vs = VariantSet(
            id="vs1", decision_key="d", prompt_template="p",
            project="proj",
            variants=[
                Variant(index=0, image_id="a", seed=1),
                Variant(index=1, image_id="b", seed=2),
            ],
        )
        s.create(vs)
        loaded = s.get("vs1")
        assert loaded is not None
        assert len(loaded.variants) == 2
        assert loaded.variants[0].seed == 1
        assert loaded.project == "proj"


def test_variant_set_lock_persisted():
    with VariantStore(":memory:") as s:
        vs = VariantSet(
            id="vs1", decision_key="d", prompt_template="p",
            variants=[Variant(index=0, image_id="a")],
        )
        s.create(vs)
        vs.lock_variant(0, locked_by="alice")
        s.save(vs)
        loaded = s.get("vs1")
        assert loaded.lock == VariantLock.LOCKED
        assert loaded.locked_index == 0
        assert loaded.locked_by == "alice"


def test_variant_store_find_by_decision():
    with VariantStore(":memory:") as s:
        s.create(VariantSet(id="v1", decision_key="d", prompt_template="p"))
        s.create(VariantSet(id="v2", decision_key="d", prompt_template="p"))
        s.create(VariantSet(id="v3", decision_key="other", prompt_template="p"))
        latest = s.find_by_decision("d")
        # v2 is the most recently inserted for decision_key "d"
        assert latest.id in ("v1", "v2")
        # v3 is a different decision
        assert s.find_by_decision("other").id == "v3"
        # And decision "missing" returns None
        assert s.find_by_decision("missing") is None


def test_plan_seeds_seed_variation():
    seeds = plan_seeds(100, 4, strategy=GenerationStrategy.SEED_VARIATION)
    assert seeds == [100, 101, 102, 103]


def test_plan_seeds_prompt_variation():
    seeds = plan_seeds(100, 4, strategy=GenerationStrategy.PROMPT_VARIATION)
    assert seeds == [100, 100, 100, 100]


# ============================================================
# References
# ============================================================


def test_pillow_backend_embed_and_similarity():
    p = Path("/tmp") / "ref_test.png"
    Image.new("RGB", (32, 32), (200, 100, 50)).save(p)
    backend = PillowBackend()
    emb = backend.embed(str(p))
    assert len(emb) == backend.dimension()
    # Embedding the same image should give similarity 1.0
    emb2 = backend.embed(str(p))
    assert abs(backend.similarity(emb, emb2) - 1.0) < 1e-6
    p.unlink()


def test_reference_library_add_and_get(tmp_path):
    img = tmp_path / "ref.png"
    Image.new("RGB", (32, 32), (50, 100, 200)).save(img)
    lib = ReferenceLibrary(tmp_path / "lib.db", storage_dir=tmp_path / "store")
    rid = lib.add(img, kind=ReferenceKind.STYLE, title="test", tags=["dark", "blue"])
    ref = lib.get(rid)
    assert ref is not None
    assert ref.title == "test"
    assert "dark" in ref.tags
    assert ref.kind == ReferenceKind.STYLE


def test_reference_library_dedup_by_hash(tmp_path):
    img = tmp_path / "ref.png"
    Image.new("RGB", (16, 16), (10, 10, 10)).save(img)
    lib = ReferenceLibrary(tmp_path / "lib.db", storage_dir=tmp_path / "store")
    rid1 = lib.add(img)
    rid2 = lib.add(img)  # same file
    assert rid1 == rid2


def test_reference_library_find_similar(tmp_path):
    # Add 3 refs: red, green, blue. Search for one similar to red.
    for color, name in [((200, 50, 50), "red.jpg"), ((50, 200, 50), "green.jpg"),
                        ((50, 50, 200), "blue.jpg")]:
        Image.new("RGB", (32, 32), color).save(tmp_path / name)
    lib = ReferenceLibrary(tmp_path / "lib.db", storage_dir=tmp_path / "store")
    for n in ["red.jpg", "green.jpg", "blue.jpg"]:
        lib.add(tmp_path / n)

    # Search with a red-ish image; the red ref should top the list.
    query = tmp_path / "query.png"
    Image.new("RGB", (32, 32), (220, 60, 60)).save(query)
    results = lib.find_similar_to_image(str(query), top_k=3)
    assert results[0][0].path.endswith("red.jpg")


def test_reference_library_use_count(tmp_path):
    img = tmp_path / "r.png"
    Image.new("RGB", (16, 16), (10, 10, 10)).save(img)
    lib = ReferenceLibrary(tmp_path / "lib.db", storage_dir=tmp_path / "store")
    rid = lib.add(img)
    lib.increment_use_count(rid)
    lib.increment_use_count(rid)
    assert lib.get(rid).use_count == 2


def test_reference_library_list_by_kind(tmp_path):
    for i, kind in enumerate([ReferenceKind.STYLE, ReferenceKind.STYLE, ReferenceKind.CHARACTER]):
        p = tmp_path / f"r{i}.png"
        Image.new("RGB", (16, 16), (i * 50, i * 50, i * 50)).save(p)
    lib = ReferenceLibrary(tmp_path / "lib.db", storage_dir=tmp_path / "store")
    for i in range(3):
        kind = ReferenceKind.STYLE if i < 2 else ReferenceKind.CHARACTER
        lib.add(tmp_path / f"r{i}.png", kind=kind)
    assert len(lib.list(kind=ReferenceKind.STYLE)) == 2
    assert len(lib.list(kind=ReferenceKind.CHARACTER)) == 1


# ============================================================
# History
# ============================================================


@pytest.fixture
def history_with_gallery(tmp_path):
    """Create a fresh history + gallery backed by distinct image files."""
    gallery = Gallery(tmp_path / "gal.db")
    history = ImageHistory(tmp_path / "hist.db")
    # Pre-create a few distinct paths
    paths = []
    for i in range(10):
        p = tmp_path / f"img_{i}.png"
        Image.new("RGB", (16, 16), (i * 20, i * 20, i * 20)).save(p)
        paths.append(p)
    yield history, gallery, paths
    history.close()
    gallery.close()


def test_history_record_and_get_current(history_with_gallery):
    history, gallery, paths = history_with_gallery
    # Need to add an image first so the FK-like relationship is real
    rec_id = gallery.add(ImageRecord(path=str(paths[0])))
    history.record("job1", rec_id, params={"seed": 1})
    cur = history.get_current("job1")
    assert cur is not None
    assert cur.image_id == rec_id
    assert cur.iteration == 1
    assert cur.is_current is True


def test_history_iteration_auto_increments(history_with_gallery):
    history, gallery, paths = history_with_gallery
    for i in range(3):
        rec_id = gallery.add(ImageRecord(path=str(paths[i])))
        history.record("job1", rec_id, params={"seed": i})
    entries = history.get_job_history("job1")
    assert [e.iteration for e in entries] == [1, 2, 3]
    # Only the last one is current
    currents = [e for e in entries if e.is_current]
    assert len(currents) == 1
    assert currents[0].iteration == 3


def test_history_set_current(history_with_gallery):
    history, gallery, paths = history_with_gallery
    ids = [gallery.add(ImageRecord(path=str(paths[i]))) for i in range(3)]
    for i, rid in enumerate(ids, 1):
        history.record("job1", rid, params={"seed": i})
    # Switch back to iteration 1
    history.set_current("job1", 1)
    cur = history.get_current("job1")
    assert cur.iteration == 1
    assert cur.image_id == ids[0]


def test_history_restore_creates_new_gallery_record(history_with_gallery):
    history, gallery, paths = history_with_gallery
    rid = gallery.add(ImageRecord(path=str(paths[0]), rating=5, tags=["hero"]))
    history.record("job1", rid, params={"seed": 42})
    # Add a newer iteration
    rid2 = gallery.add(ImageRecord(path=str(paths[1])))
    history.record("job1", rid2, iteration=2)

    # Restore iteration 1
    new_id = history.restore("job1", 1, gallery)
    restored = gallery.get(new_id)
    assert restored is not None
    assert "restored" in restored.tags
    assert restored.rating == 5  # preserved
    assert "restored" in restored.path  # file was copied with _restored suffix


def test_history_diff(history_with_gallery):
    history, gallery, paths = history_with_gallery
    rid1 = gallery.add(ImageRecord(path=str(paths[0])))
    rid2 = gallery.add(ImageRecord(path=str(paths[1])))
    history.record("job1", rid1, params={"seed": 1, "cfg": 7.0})
    history.record("job1", rid2, params={"seed": 2, "cfg": 7.0})
    d = history.diff("job1", 1, 2)
    assert d["param_diff"]["seed"] == {"a": 1, "b": 2}
    assert "cfg" not in d["param_diff"]  # unchanged


def test_history_stats(history_with_gallery):
    history, gallery, paths = history_with_gallery
    for i in range(5):
        rid = gallery.add(ImageRecord(path=str(paths[i])))
        history.record("job1", rid)
    s = history.stats("job1")
    assert s["iterations"] == 5


# ============================================================
# Views
# ============================================================


def test_gallery_view_grid(tmp_path):
    # Create 3 images
    paths = []
    for i in range(3):
        p = tmp_path / f"img_{i}.png"
        Image.new("RGB", (32, 32), (i * 80, i * 80, i * 80)).save(p)
        paths.append(p)
    records = [
        ImageRecord(
            path=str(p), prompt=f"a scene {i}", seed=i, rating=(i + 1) % 6,
            tags=[f"tag{i}"], project="proj",
        )
        for i, p in enumerate(paths)
    ]
    out = tmp_path / "view.html"
    view = GalleryView()
    result = view.render(records, out, layout=ViewLayout.GRID)  # type: ignore[arg-type]
    assert result.exists()
    html_text = result.read_text()
    assert "<!DOCTYPE html>" in html_text
    assert "Directo Gallery" in html_text
    assert "a scene 0" in html_text
    assert 'data-rating="1"' in html_text


def test_gallery_view_all_layouts(tmp_path):
    p = tmp_path / "img.png"
    Image.new("RGB", (32, 32), (50, 50, 50)).save(p)
    rec = ImageRecord(path=str(p), prompt="test")
    for layout in [ViewLayout.GRID, ViewLayout.MASONRY, ViewLayout.LIST, ViewLayout.TIMELINE]:
        out = tmp_path / f"view_{layout.value}.html"
        GalleryView().render([rec], out, layout=layout)  # type: ignore[arg-type]
        assert out.exists()
        assert f'class="{layout.value}"' in out.read_text()


def test_gallery_view_search_data_includes_all_metadata(tmp_path):
    p = tmp_path / "img.png"
    Image.new("RGB", (16, 16), (10, 10, 10)).save(p)
    rec = ImageRecord(
        path=str(p),
        prompt="a dragon in the clouds",
        notes="main character",
        tags=["fantasy", "epic"],
        model="flux-dev",
    )
    out = tmp_path / "view.html"
    GalleryView().render([rec], out)
    text = out.read_text()
    # The data-search attribute should contain all metadata
    assert "dragon" in text
    assert "fantasy" in text
    assert "flux-dev" in text
    assert "main character" in text
