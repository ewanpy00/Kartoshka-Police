import asyncio
import io
import zipfile
from datetime import UTC, datetime

from app import filters, sources
from app.submit import Entry, Submitter

PREPARED = filters.prepare([{"id": "tamm", "names": ["TAMM"], "official_domains": ["tamm.abudhabi"]},
                            {"id": "rta", "names": ["RTA"], "match_tokens": ["rta"], "official_domains": ["rta.ae"]}])


def test_feed_keeps_uae_brands_in_host_or_path():
    text = "# comment\nhttps://tamm-pay.top/x\nhttp://hacked-blog.com/wp/rta/pay.php\nhttps://paypal-login.com/\nnot a url\n"
    entries = sources.feed_entries("openphish", text, PREPARED)
    assert [(e.url, e.brand_id) for e in entries] == [("https://tamm-pay.top/x", "tamm"),
                                                      ("http://hacked-blog.com/wp/rta/pay.php", "rta")]
    assert all(e.deep for e in entries)


def test_nrd_zip_is_filtered_by_name():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("domain-names.txt", "bakery.com\nrta-fines-pay.top\ntamm-renew.xyz\n")
    entries = sources.nrd_entries(buffer.getvalue(), PREPARED)
    assert [e.url for e in entries] == ["https://rta-fines-pay.top/", "https://tamm-renew.xyz/"]
    assert sources.nrd_key(datetime(2026, 11, 23, tzinfo=UTC)) == "MjAyNi0xMS0yMy56aXA="


def test_submitter_batches_by_mode_and_keeps_entries_when_core_is_down():
    bodies = []

    async def post(body):
        bodies.append(body)

    submitter = Submitter(post=post)
    submitter.add(Entry("ct", "https://a-tamm.top/", "tamm", "name"))
    submitter.add(Entry("openphish", "https://b-tamm.top/x", "tamm", "name", deep=True))
    assert asyncio.run(submitter.flush()) == 2
    assert sorted(b["check_mode"] for b in bodies) == ["deep", "screen"]

    async def down(body):
        raise OSError("connection refused")

    failing = Submitter(post=down)
    failing.add(Entry("ct", "https://c-tamm.top/", "tamm", "name"))
    assert asyncio.run(failing.flush()) == 0 and len(failing.pending) == 1
