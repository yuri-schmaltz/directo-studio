"""Tests for the gallery."""

import sys
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from directo.gallery import Gallery, ImageRecord


@pytest.fixture
def tmp_image(tmp_path) -> Path:
    """Create a tiny valid PNG for testing."""
    p = tmp_path / "sample.png"
    Image.new("RGB", (32, 32), color=(100, 100, 100)).save(p)
    return p


@pytest.fixture
def gallery(tmp_path) -> Gallery:
    return Gallery(tmp_path / "gallery.db", image_root=tmp_path)


def test_add_and_get(gallery, tmp_image):
    rec = ImageRecord(path=str(tmp_image), prompt="a cat", model="sdxl", seed=42)
    rec_id = gallery.add(rec)
    fetched = gallery.get(rec_id)
    assert fetched.prompt == "a cat"
    assert fetched.seed == 42


def test_get_by_path(gallery, tmp_image):
    rec = ImageRecord(path=str(tmp_image))
    gallery.add(rec)
    found = gallery.get_by_path(str(tmp_image))
    assert found is not None


def test_rate(gallery, tmp_image):
    rec = ImageRecord(path=str(tmp_image))
    rid = gallery.add(rec)
    gallery.rate(rid, 4)
    assert gallery.get(rid).rating == 4
    gallery.rate(rid, 99)  # clamps
    assert gallery.get(rid).rating == 5


def test_favorite(gallery, tmp_image):
    rec = ImageRecord(path=str(tmp_image))
    rid = gallery.add(rec)
    gallery.favorite(rid)
    assert gallery.get(rid).favorite is True
    assert len(gallery.list_favorites()) == 1


def test_color_tag(gallery, tmp_image):
    rec = ImageRecord(path=str(tmp_image))
    rid = gallery.add(rec)
    gallery.set_color(rid, "blue")
    assert gallery.get(rid).color_tag == "blue"
    with pytest.raises(ValueError):
        gallery.set_color(rid, "neon")


def test_tags(gallery, tmp_image):
    rec = ImageRecord(path=str(tmp_image))
    rid = gallery.add(rec)
    gallery.add_tag(rid, "hero")
    gallery.add_tag(rid, "wide")
    gallery.add_tag(rid, "hero")  # dedup
    tags = gallery.get(rid).tags
    assert tags == ["hero", "wide"]
    gallery.remove_tag(rid, "hero")
    assert gallery.get(rid).tags == ["wide"]


def test_search_text(gallery, tmp_image):
    gallery.add(ImageRecord(path=str(tmp_image), prompt="a dragon in the clouds", seed=1))
    gallery.add(ImageRecord(path=str(tmp_image.with_name("x.png")), prompt="a cat sleeping", seed=2))
    hits = gallery.search(text="dragon")
    assert len(hits) == 1
    assert hits[0].seed == 1


def test_search_min_rating(gallery, tmp_image):
    gallery.add(ImageRecord(path=str(tmp_image), prompt="p", seed=1, rating=3))
    gallery.add(ImageRecord(path=str(tmp_image.with_name("x.png")), prompt="p", seed=2, rating=5))
    assert len(gallery.search(min_rating=4)) == 1
    assert len(gallery.search(min_rating=2)) == 2


def test_search_by_tag(gallery, tmp_image):
    rec1 = ImageRecord(path=str(tmp_image), tags=["hero", "wide"], seed=1)
    rec2 = ImageRecord(path=str(tmp_image.with_name("x.png")), tags=["hero"], seed=2)
    gallery.add(rec1)
    gallery.add(rec2)
    hits = gallery.search(tags=["hero", "wide"])
    assert len(hits) == 1
    assert hits[0].seed == 1


def test_search_filters(gallery, tmp_image):
    gallery.add(ImageRecord(path=str(tmp_image), project="alpha", model="sdxl", seed=1))
    gallery.add(ImageRecord(path=str(tmp_image.with_name("y.png")), project="beta", model="flux", seed=2))
    assert len(gallery.search(project="alpha")) == 1
    assert len(gallery.search(model="flux")) == 1
    assert len(gallery.search(project="alpha", model="flux")) == 0


def test_dedup_finds_match(gallery, tmp_image):
    gallery.add(ImageRecord(path=str(tmp_image), phash="0123456789abcdef", seed=1))
    gallery.add(ImageRecord(path=str(tmp_image.with_name("y.png")), phash="0123456789abcdee", seed=2))
    dups = gallery.find_duplicates("0123456789abcdef", max_hamming=2)
    assert len(dups) == 2  # exact + 1-bit-off


def test_dedup_no_match(gallery, tmp_image):
    gallery.add(ImageRecord(path=str(tmp_image), phash="0123456789abcdef", seed=1))
    dups = gallery.find_duplicates("ffffffffffffffff", max_hamming=2)
    assert dups == []


def test_batch_rename(tmp_path, gallery):
    files = []
    for i in range(3):
        p = tmp_path / f"original_{i}.png"
        Image.new("RGB", (16, 16), (i * 80, 0, 0)).save(p)
        files.append(p)
        gallery.add(ImageRecord(path=str(p), project="proj", seed=i, model="sdxl"))

    renames = gallery.batch_rename(
        "renamed_{index}_{model}",
        project="proj",
        dry_run=True,
    )
    assert len(renames) == 3
    # dry_run should not have moved files
    for old, _ in renames:
        assert Path(old).exists()


def test_batch_rename_apply(tmp_path, gallery):
    p = tmp_path / "orig.png"
    Image.new("RGB", (16, 16), (50, 50, 50)).save(p)
    gallery.add(ImageRecord(path=str(p), project="p", seed=7, model="sdxl"))
    renames = gallery.batch_rename("frame_{index}_{seed}", project="p", dry_run=False)
    assert len(renames) == 1
    old, new = renames[0]
    assert not Path(old).exists()
    assert Path(new).exists()
    # DB should reflect new path
    fetched = gallery.get_by_path(new)
    assert fetched is not None


def test_delete(gallery, tmp_image):
    rid = gallery.add(ImageRecord(path=str(tmp_image)))
    assert gallery.delete(rid) is True
    assert gallery.get(rid) is None


def test_stats(gallery, tmp_image):
    gallery.add(ImageRecord(path=str(tmp_image), model="sdxl", rating=5, favorite=True))
    gallery.add(ImageRecord(path=str(tmp_image.with_name("y.png")), model="flux", rating=3))
    s = gallery.stats()
    assert s["total"] == 2
    assert s["rated"] == 2
    assert s["favorites"] == 1
    assert s["top_models"][0][0] in ("sdxl", "flux")
