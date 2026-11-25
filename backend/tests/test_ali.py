from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app import jobs, settings
from app.ali import courses, executor, service
from app.ali.client import AliError, AliUncertain, FakeAli, set_client
from app.ali.models import Account, Media, PhoneLock, Slot, now
from app.store import CONTENT, NICHES, get_store

from .test_content import niche, provider  # noqa: F401

BERLIN = settings.TIMEZONE


@pytest.fixture
def ali(client, niche):  # noqa: F811
    fake = FakeAli()
    set_client(fake)
    return fake


def reel(niche, n=1):  # noqa: F811
    return [get_store().create(CONTENT, {"title": f"Reel {i}", "modelId": niche["modelId"], "nicheId": niche["id"], "type": "Reel",
                                         "status": "Approved", "step": "video", "finalReel": [f"https://cdn.example/{i}.mp4"]})["id"]
            for i in range(n)]


def account(client, niche, name="lena.gym", device="2343"):  # noqa: F811
    r = client.post("/ali/accounts", json={"username": name, "nicheId": niche["id"], "deviceId": device})
    assert r.status_code == 201, r.text
    return next(a for a in r.json()["accounts"] if a["username"] == name.lstrip("@").lower())


def slots(account_id, **where):
    with jobs.session() as s:
        rows = list(s.scalars(select(Slot).where(Slot.account_id == account_id).order_by(Slot.due)))
        return [x for x in rows if all(getattr(x, k) == v for k, v in where.items())]


def make_due(slot_id, minutes_ago=1):
    with jobs.session() as s:
        slot = s.get(Slot, slot_id)
        slot.due = now() - timedelta(minutes=minutes_ago)
        slot.window_end = slot.due + timedelta(minutes=20)
        slot.busy_until = slot.due + timedelta(minutes=slot.minutes + slot.after + 3)
        s.commit()


def state(slot_id):
    with jobs.session() as s:
        return s.get(Slot, slot_id).status


def started(client, niche, course="pdf_v1", name="lena.gym", device="2343"):  # noqa: F811
    acc = account(client, niche, name, device)
    assert client.post(f"/ali/accounts/{acc['id']}/created", json={"course": course}).status_code == 200
    assert client.post(f"/ali/accounts/{acc['id']}/armed", json={"armed": True}).status_code == 200
    return acc["id"]


def test_courses_follow_the_rules():
    t0 = datetime(2026, 11, 25, 14, 0, tzinfo=BERLIN)
    plan = courses.steps("pdf_v1", t0)
    assert plan[0][1:5] == ("warmup", 0, t0 + timedelta(minutes=3), 7)
    day1 = [p for p in plan if p[0] == 1 and p[1] == "reel"]
    assert [p[3] for p in day1] == [t0 + timedelta(minutes=40), t0 + timedelta(minutes=160)]
    day2 = [p[3].strftime("%H:%M") for p in plan if p[0] == 2 and p[1] == "reel"]
    assert day2 == ["10:00", "12:30", "15:00"]
    assert not [p for p in plan if p[1] == "status" and p[0] < 3] and len([p for p in plan if p[1] == "status"]) == 10
    assert all(p[5] == 2 and p[6] == 2 for p in plan if p[1] == "reel")  # 2 Minuten scrollen davor und danach
    gentle = courses.steps("native_7", t0)
    assert gentle[0][1] == "native_warmup" and gentle[0][4] == 20
    assert not [p for p in gentle if p[0] == 1 and p[1] == "reel"]
    second = next(p for p in gentle if p[0] == 2)
    assert second[3] - t0 >= timedelta(hours=24) and second[3].strftime("%H:%M") == "10:00"
    assert len([p for p in gentle if p[1] == "reel"]) == 6 and all(p[6] == 10 for p in gentle if p[1] == "reel")
    # Sommerzeit-Wechsel: 10 Uhr bleibt 10 Uhr Berliner Zeit
    spring = courses.steps("pdf_v1", datetime(2027, 3, 27, 9, 0, tzinfo=BERLIN))
    assert {p[3].strftime("%H:%M %z") for p in spring if p[0] == 2 and p[2] == 1 and p[1] == "reel"} == {"10:00 +0200"}


def test_account_rules(client, niche, ali):  # noqa: F811
    bad = lambda **b: client.post("/ali/accounts", json={"username": "x", "nicheId": niche["id"], "deviceId": "2343", **b})  # noqa: E731
    assert bad(username="hat leerzeichen").status_code == 409
    assert bad(deviceId="9999").status_code == 409
    account(client, niche, "@Lena.Gym")
    assert "gibt es schon" in bad(username="lena.gym").json()["detail"]
    account(client, niche, "b")
    account(client, niche, "c")
    assert "schon 3 Accounts" in bad(username="d").json()["detail"]
    get_store().update(NICHES, niche["id"], {"status": "Proposed"})
    assert "nicht freigegeben" in bad(username="e", deviceId="3996").json()["detail"]


def test_nothing_runs_until_you_switch_it_on(client, niche, ali):  # noqa: F811
    acc = account(client, niche)
    assert client.post(f"/ali/accounts/{acc['id']}/armed", json={"armed": True}).status_code == 409  # erst »erstellt«
    view = client.post(f"/ali/accounts/{acc['id']}/created", json={"course": "pdf_v1"}).json()["accounts"][0]
    assert view["courseName"] == "Schnellstart" and not view["armed"] and len(view["slots"]) == 1 + 2 + 18 + 10
    assert "nicht zurückgesetzt" in client.post(f"/ali/accounts/{acc['id']}/created", json={"course": "native_7"}).json()["detail"]
    for slot in slots(acc["id"]):
        make_due(slot.id)
    executor.tick()
    assert not ali.calls and {x.status for x in slots(acc["id"])} == {"planned"}


def test_switching_on_late_restarts_the_course_but_keeps_t0(client, niche, ali):  # noqa: F811
    acc = account(client, niche)
    client.post(f"/ali/accounts/{acc['id']}/created", json={"course": "pdf_v1"})
    with jobs.session() as s:
        row = s.get(Account, acc["id"])
        row.created_at = t0 = now() - timedelta(hours=5)
        for slot in s.scalars(select(Slot)):
            slot.due -= timedelta(hours=5)
        s.commit()
    client.post(f"/ali/accounts/{acc['id']}/armed", json={"armed": True})
    first = slots(acc["id"])[0]
    assert first.kind == "warmup" and first.due > now()
    with jobs.session() as s:
        assert abs(s.get(Account, acc["id"]).created_at - t0) < timedelta(seconds=1)


def test_warmup_then_reel_is_posted_with_receipt(client, niche, ali):  # noqa: F811
    ids = reel(niche, 2)
    aid = started(client, niche)
    warmup = slots(aid, kind="warmup")[0]
    first = slots(aid, kind="reel")[0]
    assert first.content_id == ids[0] and first.caption
    make_due(warmup.id)
    executor.tick()
    assert state(warmup.id) == "running"
    executor.tick()
    assert state(warmup.id) == "done"
    with jobs.session() as s:
        assert not list(s.scalars(select(PhoneLock)))  # Handy wieder frei
    make_due(first.id)
    executor.tick()
    executor.tick()
    assert state(first.id) == "posted"
    run = next(r for r in ali.runs.values() if "video" in r["output"])
    with jobs.session() as s:
        media = s.get(Media, ids[0])
        assert media.status == "used" and run["output"]["video"] == media.vault_id
    view = client.get("/ali").json()["accounts"][0]
    assert view["posted"] == 1 and view["reelsReady"] == 1 and view["reelsMissing"] == 18


def test_a_reel_belongs_to_one_account_only(client, niche, ali):  # noqa: F811
    ids = reel(niche, 1)
    a = started(client, niche, name="a")
    b = started(client, niche, name="b", device="3996")
    assert [x.content_id for x in slots(a, kind="reel") if x.content_id] == ids
    assert not [x for x in slots(b, kind="reel") if x.content_id]
    more = reel(niche, 1)
    executor.tick()  # neu freigegebene Reels werden einsortiert
    assert [x.content_id for x in slots(b, kind="reel") if x.content_id] == more[:1] or \
        len([x for x in slots(a, kind="reel") if x.content_id]) == 2


def test_missing_reel_is_visible_and_then_missed(client, niche, ali):  # noqa: F811
    aid = started(client, niche)
    first = slots(aid, kind="reel")[0]
    make_due(first.id)
    executor.tick()
    with jobs.session() as s:
        assert s.get(Slot, first.id).detail == "Kein freigegebenes Reel im Vorrat"
    make_due(first.id, minutes_ago=30)
    executor.tick()
    assert state(first.id) == "missed" and not [c for c in ali.calls if c[0] == "start"]
    assert client.post(f"/ali/slots/{first.id}/replan").status_code == 200 and state(first.id) == "planned"


def test_lost_start_is_never_repeated(client, niche, ali):  # noqa: F811
    reel(niche, 2)
    aid = started(client, niche)
    first, second = slots(aid, kind="reel")[:2]
    make_due(first.id)
    executor.deliver_due()
    ali.fail["start"] = AliUncertain("lost")
    executor.tick()
    assert state(first.id) == "uncertain"
    make_due(second.id)
    for _ in range(3):
        executor.tick()
    assert not [c for c in ali.calls if c[0] == "start"]  # weder wiederholt noch das nächste Reel gestartet
    with jobs.session() as s:
        assert "ungeklärt" in s.get(Slot, second.id).detail
    assert client.post(f"/ali/slots/{first.id}/replan").status_code == 409  # ungeklärt lässt sich nicht neu ansetzen
    client.post(f"/ali/slots/{first.id}/resolve", json={"outcome": "not_happened"})
    assert state(first.id) == "failed"
    with jobs.session() as s:
        assert not list(s.scalars(select(PhoneLock)))
    executor.tick()
    executor.tick()
    assert state(second.id) == "posted"


def test_stale_lock_frees_the_phone_for_other_accounts(client, niche, ali):  # noqa: F811
    aid = started(client, niche, name="a")
    bid = started(client, niche, name="b")
    wa, wb = slots(aid, kind="warmup")[0], slots(bid, kind="warmup")[0]
    make_due(wa.id, minutes_ago=18)
    ali.fail["start"] = AliUncertain("lost")
    executor.tick()
    assert state(wa.id) == "uncertain"
    make_due(wb.id)
    executor.tick()
    executor.tick()
    assert state(wb.id) == "done" and state(wa.id) == "uncertain"


def test_unverified_post_waits_for_you(client, niche, ali):  # noqa: F811
    ids = reel(niche, 1)
    aid = started(client, niche)
    first = slots(aid, kind="reel")[0]
    make_due(first.id)
    ali.output = {"verified": False}
    executor.tick()
    executor.tick()
    assert state(first.id) == "uncertain"
    for _ in range(3):
        executor.tick()
    assert len([c for c in ali.calls if c[0] == "start"]) == 1
    client.post(f"/ali/slots/{first.id}/resolve", json={"outcome": "happened"})
    assert state(first.id) == "posted"
    with jobs.session() as s:
        assert s.get(Media, ids[0]).status == "used"


@pytest.mark.parametrize("output", [{"posts_after": 3}, {"video": "anderes"}, {"account": "fremd"}, {"slot_id": "x"},
                                    {"status": "SHARED_UNVERIFIED"}, {"after_scroll": "skipped"}])
def test_receipt_must_match_exactly(client, niche, ali, output):  # noqa: F811
    reel(niche, 1)
    aid = started(client, niche)
    first = slots(aid, kind="reel")[0]
    make_due(first.id)
    ali.output = output
    executor.tick()
    executor.tick()
    assert state(first.id) == "uncertain"


def test_stop_switch_and_definite_reject(client, niche, ali):  # noqa: F811
    aid = started(client, niche)
    warmup = slots(aid, kind="warmup")[0]
    make_due(warmup.id)
    assert client.post("/ali/stop", json={"stopped": True}).json()["stopped"] is True
    executor.tick()
    assert state(warmup.id) == "planned" and not ali.calls
    client.post("/ali/stop", json={"stopped": False})
    ali.fail["start"] = AliError("422", 422)
    executor.tick()
    assert state(warmup.id) == "failed"
    with jobs.session() as s:
        assert not list(s.scalars(select(PhoneLock)))


def test_account_problem_pauses_the_automation(client, niche, ali):  # noqa: F811
    aid = started(client, niche)
    check = slots(aid, kind="status")[0]
    make_due(check.id)
    ali.output = {"account_status": "logged_out"}
    executor.tick()
    executor.tick()
    view = client.get("/ali").json()["accounts"][0]
    assert not view["armed"] and "ausgeloggt" in view["note"] and state(check.id) == "failed"


def test_one_phone_does_one_thing(client, niche, ali):  # noqa: F811
    aid = started(client, niche, name="a")
    bid = started(client, niche, name="b")
    with jobs.session() as s:
        spans = sorted((x.due - timedelta(minutes=x.before), x.busy_until) for x in s.scalars(select(Slot)))
    assert all(spans[i][1] <= spans[i + 1][0] for i in range(len(spans) - 1))  # der Plan überschneidet sich nie
    wa, wb = slots(aid, kind="warmup")[0], slots(bid, kind="warmup")[0]
    make_due(wa.id, 2)
    make_due(wb.id, 1)
    executor.dispatch_due()
    assert sorted([state(wa.id), state(wb.id)]) == ["planned", "running"]
    ali.busy.add("2343")
    executor.poll_running()
    executor.dispatch_due()
    assert state(wb.id) == "planned"
    ali.busy.clear()
    executor.dispatch_due()
    assert state(wb.id) == "running"


def test_vault_trouble_is_retried_with_the_same_key(client, niche, ali):  # noqa: F811
    reel(niche, 1)
    aid = started(client, niche)
    first = slots(aid, kind="reel")[0]
    make_due(first.id)
    ali.fail["import"] = AliUncertain("timeout")
    executor.deliver_due()
    assert not slots(aid, kind="reel")[0].vault_id
    executor.deliver_due()
    assert slots(aid, kind="reel")[0].vault_id and len(ali.vault) == 1


def test_gentle_course_needs_the_native_account(client, niche, ali):  # noqa: F811
    aid = started(client, niche, course="native_7")
    warmup = slots(aid, kind="native_warmup")[0]
    make_due(warmup.id)
    executor.tick()
    with jobs.session() as s:
        assert "nicht als Instagram-Konto hinterlegt" in s.get(Slot, warmup.id).detail
        s.get(Account, aid).native_id = "n1"
        s.commit()
    executor.tick()
    executor.tick()
    assert state(warmup.id) == "done"


def test_remove_and_skip(client, niche, ali):  # noqa: F811
    ids = reel(niche, 1)
    aid = started(client, niche)
    first = slots(aid, kind="reel")[0]
    client.post(f"/ali/slots/{first.id}/skip")
    assert state(first.id) == "cancelled"
    with jobs.session() as s:
        assert s.get(Media, ids[0]) is None  # das Reel ist wieder frei
    assert client.delete(f"/ali/accounts/{aid}").json()["accounts"] == []
    assert client.get("/ali").json()["devices"][0]["id"] == "2343"
