"""The pet simulation: stats over time, life stages, moods and the care actions."""

import pytest

import pet

MINUTE = 60
DAY = 24 * 60 * MINUTE


def grown_pet(**stats):
    """A two-day-old (adult) pet, updated right now, with optional stat overrides."""
    p = pet.new_pet("Test")
    now = p["last_update"]
    p["born_at"] = now - 2 * DAY
    p.update(stats)
    return p, now


# ---------- time and stats ----------
def test_stats_drop_over_time():
    p, now = grown_pet()
    pet.tick(p, now + 60 * MINUTE)
    assert p["hunger"] == pytest.approx(80 - 60 * pet.HUNGER_DECAY)
    assert p["happiness"] == pytest.approx(80 - 60 * pet.HAPPY_DECAY)
    assert p["energy"] == pytest.approx(100 - 60 * pet.ENERGY_DECAY)


def test_sleeping_slows_hunger_and_restores_energy():
    p, now = grown_pet(sleeping=True, energy=50.0)
    pet.tick(p, now + 10 * MINUTE)
    assert p["hunger"] == pytest.approx(80 - 10 * pet.HUNGER_DECAY * pet.SLEEP_DECAY_FACTOR)
    assert p["energy"] == pytest.approx(50 + 10 * pet.ENERGY_REGEN)


def test_stats_stay_between_0_and_100():
    p, now = grown_pet(sleeping=True, energy=99.0)
    pet.tick(p, now + 600 * MINUTE)
    for key in ("hunger", "happiness", "energy", "health"):
        assert 0 <= p[key] <= 100


def test_poops_appear_and_are_capped():
    p, now = grown_pet()
    pet.tick(p, now + pet.POOP_EVERY_MIN * MINUTE)
    assert p["poops"] == 1
    pet.tick(p, now + 20 * pet.POOP_EVERY_MIN * MINUTE)
    assert p["poops"] == pet.MAX_POOPS


def test_long_neglect_is_fatal():
    p, now = grown_pet()
    pet.tick(p, now + 3 * DAY)
    assert p["alive"] is False


def test_eggs_do_not_change():
    p = pet.new_pet("Egg")
    now = p["born_at"]
    pet.tick(p, now + 30)  # still an egg (younger than a minute)
    assert p["hunger"] == 80.0 and p["poops"] == 0


# ---------- stages and moods ----------
@pytest.mark.parametrize("age_minutes, stage", [(0.5, "egg"), (30, "baby"), (120, "child"), (2 * 24 * 60, "adult")])
def test_life_stages(age_minutes, stage):
    p = pet.new_pet()
    assert pet.stage_of(p, p["born_at"] + age_minutes * MINUTE) == stage


@pytest.mark.parametrize("stats, mood", [
    ({"alive": False}, "dead"),
    ({"sleeping": True, "hunger": 0.0}, "sleeping"),  # sleeping wins over hunger
    ({"health": 10.0, "hunger": 0.0}, "sick"),  # sick wins over hunger
    ({"poops": 3}, "sick"),
    ({"hunger": 10.0}, "hungry"),
    ({"energy": 10.0}, "tired"),
    ({"happiness": 10.0}, "sad"),
    ({"hunger": 90.0, "happiness": 90.0}, "happy"),
    ({"hunger": 50.0}, "ok"),
])
def test_moods(stats, mood):
    p, _ = grown_pet(**stats)
    assert pet.mood_of(p, "adult") == mood


# ---------- actions ----------
def test_feed_play_clean():
    p, _ = grown_pet(hunger=50.0, poops=2)
    assert pet._apply(p, "feed") == "YUM!" and p["hunger"] == 75
    assert pet._apply(p, "play") == "YAY!" and p["happiness"] == 100 and p["energy"] == 90
    assert pet._apply(p, "clean") == "SPARKLY!" and p["poops"] == 0
    assert pet._apply(p, "clean") == "ALL CLEAN"


def test_feeding_a_full_pet_upsets_it():
    p, _ = grown_pet(hunger=99.0, happiness=50.0)
    assert pet._apply(p, "feed") == "TOO FULL!"
    assert p["happiness"] == 45


def test_sleep_toggles_and_blocks_other_actions():
    p, _ = grown_pet()
    assert pet._apply(p, "sleep") == "GOOD NIGHT"
    with pytest.raises(pet.ActionError, match="ZZZ"):
        pet._apply(p, "feed")
    assert pet._apply(p, "sleep") == "GOOD MORNING"


@pytest.mark.parametrize("stats, action, error", [
    ({"energy": 5.0}, "play", "TOO TIRED"),
    ({"alive": False}, "feed", "R.I.P."),
    ({}, "dance", "UNKNOWN"),
])
def test_refused_actions(stats, action, error):
    p, _ = grown_pet(**stats)
    with pytest.raises(pet.ActionError, match=error):
        pet._apply(p, action)


def test_an_egg_cannot_be_fed():
    with pytest.raises(pet.ActionError, match="EGG"):
        pet._apply(pet.new_pet(), "feed")


def test_public_view_hides_internals_and_rounds():
    p, _ = grown_pet(hunger=33.4, reaction={"mood": "happy", "until": 0})
    view = pet.public_view(p)
    assert "poop_timer" not in view and "reaction" not in view
    assert view["hunger"] == 33 and view["stage"] == "adult"
