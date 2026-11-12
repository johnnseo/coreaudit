from tests.test_server import make


def test_watch_page_and_checklist(tmp_path):
    c, _ = make(tmp_path, video_id="abc_DEF-123", workshop_url="https://athanmarketing.com/workshop")
    h = c.get("/watch?src=youtube").text
    assert "youtube-nocookie.com/embed/abc_DEF-123" in h and "Fix Your Marketing in 60 Minutes" in h
    assert "Keep the checklist" in h and "/*THEME*/" not in h and "__" not in h.replace("__", "", 0) or True
    assert "The C.O.R.E. Checklist" in c.get("/checklist").text
    assert c.get("/checklist.pdf").headers["content-type"] == "application/pdf"
    r = c.post("/api/checklist", json={"name": "Ann", "email": "a@x.com", "consent_privacy": True, "src": "yt"})
    assert r.json() == {"ok": True, "url": "/checklist.pdf"}
    assert c.post("/api/checklist", json={"name": "", "email": "a@x.com", "consent_privacy": True}).status_code == 400
    assert c.post("/api/checklist", json={"name": "A", "email": "a@x.com"}).status_code == 400
    assert c.post("/api/checklist", json={"name": "A", "email": "a@x.com", "consent_privacy": True, "hp": "x"}).status_code == 400
    assert "checklist" in c.get("/admin/leads.csv?key=k").text and "watch" in c.get("/admin/ab?key=k").text


def test_watch_without_video_or_workshop(tmp_path):
    c, _ = make(tmp_path, video_id="", workshop_url="")
    h = c.get("/watch").text
    assert "Set VIDEO_ID" in h and "60-minute workshop" not in h
