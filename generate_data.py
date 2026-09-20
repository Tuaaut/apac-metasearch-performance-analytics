"""Generate reproducible, linked synthetic APAC metasearch data with no dependencies."""

from __future__ import annotations

import argparse
import csv
import random
from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path


ROOT = Path(__file__).resolve().parent
CHANNELS = (
    "Google Hotel Ads", "Google Flights", "Skyscanner", "Trivago", "Wego"
)
MARKETS = {
    "TH": {"traffic": 1.0, "cpc": 0.75, "cvr": 0.090, "value": 165},
    "ID": {"traffic": 1.55, "cpc": 0.43, "cvr": 0.062, "value": 105},
    "SG": {"traffic": 0.48, "cpc": 1.35, "cvr": 0.057, "value": 310},
}
PRODUCTS = {
    "Google Hotel Ads": "hotel", "Google Flights": "flight",
    "Skyscanner": "flight", "Trivago": "hotel", "Wego": "activity",
}
LANDING = {"hotel": "/hotel/detail", "flight": "/flight/search", "activity": "/activity/search"}
DESTINATIONS = {
    "TH": ("Bangkok", "Phuket", "Chiang Mai"),
    "ID": ("Jakarta", "Bali", "Yogyakarta"),
    "SG": ("Singapore", "Bali", "Bangkok"),
}
FIELDS = {
    "ad_platform_performance": ("date", "market", "channel", "campaign_id", "campaign_name", "device_type", "impressions", "clicks", "ad_spend", "conversions"),
    "ad_click_events": ("click_id", "event_timestamp", "campaign_id", "market", "channel", "device_type", "landing_page", "session_id"),
    "user_sessions": ("session_id", "user_id", "session_start_timestamp", "market", "device_type", "traffic_source", "is_new_user"),
    "bookings": ("booking_id", "user_id", "session_id", "booking_timestamp", "product_type", "destination", "booking_value", "commission_rate", "gross_margin", "booking_status", "payment_status"),
    "experiment_assignments": ("experiment_id", "user_id", "market", "channel", "experiment_group", "assignment_timestamp", "eligible_flag"),
    "experiment_user_outcomes": ("experiment_id", "user_id", "test_ad_exposed", "test_ad_clicked", "click_id", "click_timestamp", "session_id", "session_start_timestamp", "session_source", "booking_id", "booking_timestamp", "booking_status", "payment_status", "booking_value"),
}

EXPERIMENT_USERS_PER_ARM = 5_000


def write_csv(output: Path, name: str, rows: list[dict]) -> None:
    with (output / f"{name}.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS[name])
        writer.writeheader()
        writer.writerows(rows)


def consume_legacy_experiment_draws(rng: random.Random, market: str, config: dict) -> None:
    """Keep the non-experiment synthetic campaign population deterministic.

    Earlier versions generated a summary experiment inside the campaign loop.
    Consuming the same random draws retains the existing campaign, click,
    session, and booking records while the experiment is rebuilt separately at
    user level.
    """
    baseline = {"TH": 0.050, "ID": 0.045, "SG": 0.054}[market]
    for group in ("Treatment", "Control"):
        eligible = 20_000 if market == "SG" else 50_000
        lift = 1.18 if group == "Treatment" else 1.0
        conversion_count = round(eligible * baseline * lift * rng.uniform(0.985, 1.015))
        _ = round(conversion_count * config["value"] * rng.uniform(0.96, 1.04), 2)


def generate_experiment_population(seed: int, start: date, days: int) -> tuple[list[dict], list[dict]]:
    """Create a separately identifiable, user-level randomized experiment.

    The campaign attribution population remains isolated. Every assigned user
    has one optional experiment journey/outcome row, so the Gold mart can
    prove the denominator, the observed outcome, and the group aggregation.
    """
    rng = random.Random(f"{seed}:experiment-user-level")
    assignments: list[dict] = []
    outcomes: list[dict] = []
    user_number = click_number = session_number = booking_number = 0
    assignment_at = datetime.combine(start, time(0, 0))

    for market, config in MARKETS.items():
        baseline = {"TH": 0.050, "ID": 0.045, "SG": 0.054}[market]
        for channel_index, channel in enumerate(CHANNELS, start=1):
            experiment_id = f"EXP-{market}-{channel_index:02d}"
            for group in ("Treatment", "Control"):
                conversion_probability = baseline * (1.18 if group == "Treatment" else 1.0)
                conversion_count = round(
                    EXPERIMENT_USERS_PER_ARM * conversion_probability * rng.uniform(0.985, 1.015)
                )
                converters = set(rng.sample(range(EXPERIMENT_USERS_PER_ARM), conversion_count))

                for participant in range(EXPERIMENT_USERS_PER_ARM):
                    user_number += 1
                    user_id = f"EXPUSR{user_number:07d}"
                    assignments.append({
                        "experiment_id": experiment_id,
                        "user_id": user_id,
                        "market": market,
                        "channel": channel,
                        "experiment_group": group,
                        "assignment_timestamp": assignment_at.isoformat(sep=" "),
                        "eligible_flag": "1",
                    })

                    # Intent-to-treat assignment controls the denominator. A
                    # Treatment user can be assigned to the test without a
                    # click, while a Control user can still visit organically.
                    exposed = group == "Treatment"
                    clicked = exposed and rng.random() < 0.22
                    converted = participant in converters
                    has_session = clicked or converted or rng.random() < 0.24

                    click_id = click_timestamp = ""
                    session_id = session_start_timestamp = ""
                    session_source = "none"
                    if has_session:
                        journey_day = rng.randrange(days)
                        journey_at = assignment_at + timedelta(
                            days=journey_day, hours=rng.randrange(6, 23),
                            minutes=rng.randrange(60), seconds=rng.randrange(60),
                        )
                        session_number += 1
                        session_id = f"EXPSES{session_number:07d}"
                        if clicked:
                            click_number += 1
                            click_id = f"EXPCLK{click_number:07d}"
                            click_timestamp = journey_at.isoformat(sep=" ")
                            session_at = journey_at + timedelta(seconds=rng.randrange(1, 180))
                            session_source = "test_ad_click"
                        else:
                            session_at = journey_at
                            session_source = "organic_or_direct"
                        session_start_timestamp = session_at.isoformat(sep=" ")
                    else:
                        session_at = None

                    booking_id = booking_timestamp = ""
                    booking_status = "not_booked"
                    payment_status = "not_applicable"
                    booking_value = Decimal("0.00")
                    if converted:
                        if session_at is None:
                            raise AssertionError("Converted experiment user must have a session")
                        booking_number += 1
                        booking_id = f"EXPBKG{booking_number:07d}"
                        booking_at = session_at + timedelta(hours=rng.randrange(1, 73))
                        booking_timestamp = booking_at.isoformat(sep=" ")
                        booking_status = "confirmed"
                        payment_status = "paid"
                        booking_value = Decimal(str(round(config["value"] * rng.uniform(0.65, 1.5), 2)))

                    outcomes.append({
                        "experiment_id": experiment_id,
                        "user_id": user_id,
                        "test_ad_exposed": "1" if exposed else "0",
                        "test_ad_clicked": "1" if clicked else "0",
                        "click_id": click_id,
                        "click_timestamp": click_timestamp,
                        "session_id": session_id,
                        "session_start_timestamp": session_start_timestamp,
                        "session_source": session_source,
                        "booking_id": booking_id,
                        "booking_timestamp": booking_timestamp,
                        "booking_status": booking_status,
                        "payment_status": payment_status,
                        "booking_value": f"{booking_value:.2f}",
                    })
    return assignments, outcomes


def generate(output: Path, seed: int, start: date, days: int) -> None:
    rng = random.Random(seed)
    output.mkdir(parents=True, exist_ok=True)
    platform, clicks, sessions, bookings = [], [], [], []
    known_users: dict[str, list[str]] = defaultdict(list)
    click_num = session_num = booking_num = user_num = 0

    for market, config in MARKETS.items():
        for channel_index, channel in enumerate(CHANNELS):
            campaign_number = list(MARKETS).index(market) * len(CHANNELS) + channel_index + 1
            campaign_id = f"CMP{campaign_number:03d}"
            campaign_name = f"{market} {channel} Always On"
            product = PRODUCTS[channel]
            channel_factor = (1.14, 0.91, 1.04, 0.96, 0.83)[channel_index]

            for day_offset in range(days):
                day = start + timedelta(days=day_offset)
                weekend_factor = 1.13 if day.weekday() >= 5 else 1.0
                for device in ("mobile", "desktop"):
                    mobile = device == "mobile"
                    impressions = round(1150 * config["traffic"] * channel_factor * weekend_factor
                                        * (1.35 if mobile else 0.65) * rng.uniform(0.82, 1.18))
                    ctr = 0.037 if mobile else 0.026
                    if campaign_id == "CMP003":
                        ctr *= 1.85
                    click_count = max(1, round(impressions * ctr * rng.uniform(0.88, 1.12)))
                    cpc = config["cpc"] * (1.08 if mobile else 0.92) * rng.uniform(0.9, 1.1)
                    spend = round(click_count * cpc, 2)
                    confirmed_count = 0

                    for _ in range(click_count):
                        click_num += 1
                        clicked_at = datetime.combine(day, time(rng.randrange(6, 23), rng.randrange(60), rng.randrange(60)))
                        session_id = ""
                        # Some paid clicks bounce before a first-party session is recorded.
                        if rng.random() < 0.90:
                            session_num += 1
                            session_id = f"SES{session_num:07d}"
                            if known_users[market] and rng.random() < 0.32:
                                user_id = rng.choice(known_users[market])
                                is_new = 0
                            else:
                                user_num += 1
                                user_id = f"USR{user_num:07d}"
                                known_users[market].append(user_id)
                                is_new = 1
                            session_start = clicked_at + timedelta(seconds=rng.randrange(1, 180))
                            sessions.append({
                                "session_id": session_id, "user_id": user_id,
                                "session_start_timestamp": session_start.isoformat(sep=" "),
                                "market": market, "device_type": device,
                                "traffic_source": "paid_metasearch", "is_new_user": is_new,
                            })

                            cvr = config["cvr"] * (0.82 if mobile else 1.18)
                            if campaign_id == "CMP003":
                                cvr *= 0.26  # Deliberate high CTR / low CVR investigation case.
                            if rng.random() < cvr:
                                booking_num += 1
                                booking_at = session_start + timedelta(hours=rng.randrange(1, 73))
                                value = round(config["value"] * rng.uniform(0.65, 1.5), 2)
                                commission = {"hotel": 0.15, "flight": 0.07, "activity": 0.19}[product]
                                status = rng.choices(
                                    ("confirmed", "cancelled", "pending"), weights=(88, 8, 4)
                                )[0]
                                payment = "paid" if status == "confirmed" else (
                                    "refunded" if status == "cancelled" else "pending"
                                )
                                margin = (
                                    (Decimal(str(value)) * Decimal(str(commission))).quantize(
                                        Decimal("0.01"), rounding=ROUND_HALF_UP
                                    ) if status == "confirmed" else Decimal("0.00")
                                )
                                bookings.append({
                                    "booking_id": f"BKG{booking_num:07d}", "user_id": user_id,
                                    "session_id": session_id,
                                    "booking_timestamp": booking_at.isoformat(sep=" "),
                                    "product_type": product,
                                    "destination": rng.choice(DESTINATIONS[market]),
                                    "booking_value": f"{value:.2f}",
                                    "commission_rate": f"{commission:.2f}",
                                    "gross_margin": f"{margin:.2f}",
                                    "booking_status": status, "payment_status": payment,
                                })
                                if status == "confirmed":
                                    confirmed_count += 1

                        clicks.append({
                            "click_id": f"CLK{click_num:07d}",
                            "event_timestamp": clicked_at.isoformat(sep=" "),
                            "campaign_id": campaign_id, "market": market,
                            "channel": channel, "device_type": device,
                            "landing_page": LANDING[product], "session_id": session_id,
                        })

                    platform.append({
                        "date": day.isoformat(), "market": market, "channel": channel,
                        "campaign_id": campaign_id, "campaign_name": campaign_name,
                        "device_type": device, "impressions": impressions,
                        "clicks": click_count, "ad_spend": f"{spend:.2f}",
                        "conversions": confirmed_count,
                    })

            consume_legacy_experiment_draws(rng, market, config)

    # Organic sessions make the first-party table realistic and require careful paid attribution.
    organic_count = round(len(sessions) * 0.04)
    for _ in range(organic_count):
        market = rng.choice(tuple(MARKETS))
        session_num += 1
        user_num += 1
        day = start + timedelta(days=rng.randrange(days))
        sessions.append({
            "session_id": f"SES{session_num:07d}", "user_id": f"USR{user_num:07d}",
            "session_start_timestamp": datetime.combine(day, time(12, rng.randrange(60))).isoformat(sep=" "),
            "market": market, "device_type": rng.choice(("mobile", "desktop")),
            "traffic_source": "organic", "is_new_user": 1,
        })

    assignments, outcomes = generate_experiment_population(seed, start, days)
    legacy_experiment_summary = output / "incrementality_experiment.csv"
    if legacy_experiment_summary.exists():
        legacy_experiment_summary.unlink()

    for name, rows in zip(FIELDS, (platform, clicks, sessions, bookings, assignments, outcomes)):
        write_csv(output, name, rows)
        print(f"{name}: {len(rows):,} rows")
    validate(output)


def read_csv(output: Path, name: str) -> list[dict]:
    with (output / f"{name}.csv").open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def validate(output: Path) -> None:
    platform, clicks, sessions, bookings, assignments, outcomes = (
        read_csv(output, name) for name in FIELDS
    )
    for name, rows in zip(FIELDS, (platform, clicks, sessions, bookings, assignments, outcomes)):
        assert all(tuple(row) == FIELDS[name] for row in rows), f"Invalid columns: {name}"
    assert len({r["click_id"] for r in clicks}) == len(clicks)
    assert len({r["session_id"] for r in sessions}) == len(sessions)
    assert len({r["booking_id"] for r in bookings}) == len(bookings)
    click_grain = Counter((r["event_timestamp"][:10], r["market"], r["channel"], r["campaign_id"], r["device_type"]) for r in clicks)
    assert len({(r["date"], r["market"], r["channel"], r["campaign_id"], r["device_type"]) for r in platform}) == len(platform)
    assert all(click_grain[(r["date"], r["market"], r["channel"], r["campaign_id"], r["device_type"])] == int(r["clicks"]) for r in platform)
    session_by_id = {r["session_id"]: r for r in sessions}
    assert all(not r["session_id"] or r["session_id"] in session_by_id for r in clicks)
    assert all(not r["session_id"] or (r["market"] == session_by_id[r["session_id"]]["market"] and r["device_type"] == session_by_id[r["session_id"]]["device_type"] and r["event_timestamp"] <= session_by_id[r["session_id"]]["session_start_timestamp"]) for r in clicks)
    assert all(r["session_id"] in session_by_id and r["user_id"] == session_by_id[r["session_id"]]["user_id"] for r in bookings)
    assert all(r["booking_timestamp"] >= session_by_id[r["session_id"]]["session_start_timestamp"] for r in bookings)
    assert all(Decimal(r["gross_margin"]) == (
        (Decimal(r["booking_value"]) * Decimal(r["commission_rate"])).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        ) if r["booking_status"] == "confirmed" else Decimal("0.00")
    ) for r in bookings)
    assert all(r["booking_status"] != "confirmed" or r["payment_status"] == "paid" for r in bookings)
    assert all(int(r["conversions"]) <= int(r["clicks"]) <= int(r["impressions"]) for r in platform)
    assignment_key = {(r["experiment_id"], r["user_id"]) for r in assignments}
    outcome_key = {(r["experiment_id"], r["user_id"]) for r in outcomes}
    assert len(assignment_key) == len(assignments)
    assert len(outcome_key) == len(outcomes)
    assert assignment_key == outcome_key
    assert len({r["user_id"] for r in assignments}) == len(assignments)
    experiment_ids = {r["experiment_id"] for r in assignments}
    assert len(experiment_ids) == len(MARKETS) * len(CHANNELS)
    for experiment_id in experiment_ids:
        arms = [r for r in assignments if r["experiment_id"] == experiment_id]
        assert len(arms) == 2 * EXPERIMENT_USERS_PER_ARM
        assert sum(r["experiment_group"] == "Treatment" for r in arms) == EXPERIMENT_USERS_PER_ARM
        assert sum(r["experiment_group"] == "Control" for r in arms) == EXPERIMENT_USERS_PER_ARM
    assignment_by_key = {(r["experiment_id"], r["user_id"]): r for r in assignments}
    assert len({r["click_id"] for r in outcomes if r["click_id"]}) == sum(bool(r["click_id"]) for r in outcomes)
    assert len({r["session_id"] for r in outcomes if r["session_id"]}) == sum(bool(r["session_id"]) for r in outcomes)
    assert len({r["booking_id"] for r in outcomes if r["booking_id"]}) == sum(bool(r["booking_id"]) for r in outcomes)
    for outcome in outcomes:
        assignment = assignment_by_key[(outcome["experiment_id"], outcome["user_id"])]
        treatment = assignment["experiment_group"] == "Treatment"
        exposed = outcome["test_ad_exposed"] == "1"
        clicked = outcome["test_ad_clicked"] == "1"
        has_session = bool(outcome["session_id"])
        converted = outcome["booking_status"] == "confirmed"
        assert exposed == treatment
        assert not clicked or exposed
        assert clicked == bool(outcome["click_id"])
        assert clicked == bool(outcome["click_timestamp"])
        assert not clicked or has_session
        assert has_session == bool(outcome["session_start_timestamp"])
        assert outcome["session_source"] in ("test_ad_click", "organic_or_direct", "none")
        assert (outcome["session_source"] == "none") == (not has_session)
        assert (outcome["session_source"] == "test_ad_click") == clicked
        assert converted == bool(outcome["booking_id"])
        assert converted == bool(outcome["booking_timestamp"])
        assert converted == (outcome["payment_status"] == "paid")
        assert (not converted) == (outcome["payment_status"] == "not_applicable")
        assert Decimal(outcome["booking_value"]) > 0 if converted else Decimal(outcome["booking_value"]) == 0
        if clicked:
            assert outcome["click_timestamp"] >= assignment["assignment_timestamp"]
            assert outcome["click_timestamp"] <= outcome["session_start_timestamp"]
        if converted:
            assert outcome["booking_timestamp"] >= outcome["session_start_timestamp"]
    # The synthetic scenario deliberately models a positive treatment effect.
    # This is a generator expectation, not a production experiment gate.
    converted_by_arm = Counter(
        (assignment_by_key[(outcome["experiment_id"], outcome["user_id"])]["experiment_id"],
         assignment_by_key[(outcome["experiment_id"], outcome["user_id"])]["experiment_group"])
        for outcome in outcomes if outcome["booking_status"] == "confirmed"
    )
    assert all(
        converted_by_arm[(experiment_id, "Treatment")]
        > converted_by_arm[(experiment_id, "Control")]
        for experiment_id in experiment_ids
    )
    click_by_session = {r["session_id"]: r for r in clicks if r["session_id"]}
    assert len(click_by_session) == sum(bool(r["session_id"]) for r in clicks)
    paid_sessions = set(click_by_session)
    confirmed_by_session = {r["session_id"] for r in bookings if r["booking_status"] == "confirmed" and r["payment_status"] == "paid"}
    assert sum(int(r["conversions"]) for r in platform) == len(confirmed_by_session & paid_sessions)
    conversion_grain = Counter((click_by_session[s]["event_timestamp"][:10], click_by_session[s]["market"], click_by_session[s]["channel"], click_by_session[s]["campaign_id"], click_by_session[s]["device_type"]) for s in confirmed_by_session & paid_sessions)
    assert all(conversion_grain[(r["date"], r["market"], r["channel"], r["campaign_id"], r["device_type"])] == int(r["conversions"]) for r in platform)
    print("Validation passed: schema, keys, joins, click totals, conversion totals, margin, user-level experiment assignment and outcomes")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "data")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--start-date", type=date.fromisoformat, default=date(2026, 8, 1))
    parser.add_argument("--days", type=int, default=31)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    if args.validate_only:
        validate(args.output)
    else:
        if args.days < 1:
            parser.error("--days must be at least 1")
        generate(args.output, args.seed, args.start_date, args.days)
