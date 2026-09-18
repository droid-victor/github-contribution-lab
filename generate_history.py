import os
import random
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timedelta


# ============================================================
# CONFIGURATION
# ============================================================

START = datetime(2022, 9, 18)
END = datetime(2026, 9, 18)

TIMEZONE = "+05:30"

ACTIVITY_FILE = "synthetic_activity.txt"

# True  -> calculate statistics only
# False -> actually create Git commits
DRY_RUN = True

# Reproducible research experiment
SEED = 42


# ------------------------------------------------------------
# Activity probabilities
# ------------------------------------------------------------

# Each year gets a random value inside these ranges.
WEEKDAY_PROB_RANGE = (0.65, 0.85)
WEEKEND_PROB_RANGE = (0.15, 0.35)


# ------------------------------------------------------------
# Monthly variation
# ------------------------------------------------------------

MONTH_MULT_RANGE = (0.80, 1.35)


# ------------------------------------------------------------
# Spike days
# ------------------------------------------------------------

SPIKE_PROB = 0.04
SPIKE_RANGE = (10, 25)


# ------------------------------------------------------------
# Breaks / vacations
# ------------------------------------------------------------

BREAKS_PER_YEAR = (2, 4)
BREAK_LENGTH = (5, 14)


# ------------------------------------------------------------
# Commit time distribution
# ------------------------------------------------------------

LATE_NIGHT_PROB = 0.12


# ------------------------------------------------------------
# Normal commit counts
# ------------------------------------------------------------

NORMAL_COUNTS = [
    1, 2, 3, 4, 5, 6, 7, 8
]

NORMAL_WEIGHTS = [
    9, 15, 19, 18, 14, 11, 8, 6
]


# ------------------------------------------------------------
# Safety limit
# ------------------------------------------------------------

MAX_TOTAL_COMMITS = 10000


# ============================================================
# RANDOM GENERATOR
# ============================================================

random.seed(SEED)


# ============================================================
# HELPERS
# ============================================================

def build_year_rates(start, end):
    """
    Give each year its own weekday/weekend activity rate.
    """

    rates = {}

    for year in range(start.year, end.year + 1):
        weekday_probability = random.uniform(
            *WEEKDAY_PROB_RANGE
        )

        weekend_probability = random.uniform(
            *WEEKEND_PROB_RANGE
        )

        rates[year] = (
            weekday_probability,
            weekend_probability
        )

    return rates


def build_month_multipliers(start, end):
    """
    Give every month a different activity multiplier.
    """

    multipliers = {}

    for year in range(start.year, end.year + 1):
        for month in range(1, 13):

            multipliers[(year, month)] = random.uniform(
                *MONTH_MULT_RANGE
            )

    return multipliers


def build_breaks(start, end):
    """
    Generate vacation/holiday periods.

    Returns a set containing dates that should have
    no synthetic activity.
    """

    break_dates = set()

    for year in range(start.year, end.year + 1):

        number_of_breaks = random.randint(
            *BREAKS_PER_YEAR
        )

        for _ in range(number_of_breaks):

            # Keep generated break starts inside the year.
            start_of_year = datetime(year, 1, 1)

            random_day = random.randint(0, 350)

            break_start = (
                start_of_year +
                timedelta(days=random_day)
            )

            break_length = random.randint(
                *BREAK_LENGTH
            )

            for offset in range(break_length):

                date = (
                    break_start +
                    timedelta(days=offset)
                ).date()

                break_dates.add(date)

    return break_dates


def generate_commit_times(day, count):
    """
    Generate commit timestamps for one active day.

    Most commits:
        10:00 - 19:59

    Some commits:
        22:00 - 23:59
        00:00 - 00:59
    """

    timestamps = []

    for _ in range(count):

        if random.random() < LATE_NIGHT_PROB:

            # Late-night activity.
            # 00:00-00:59 is represented as the same
            # calendar day here rather than using hour=24.
            hour = random.choice([
                0,
                22,
                23
            ])

        else:

            hour = random.choices(
                population=list(range(10, 20)),
                weights=[
                    5, 8, 10, 9, 10,
                    11, 10, 8, 6, 4
                ]
            )[0]

        minute = random.randint(0, 59)
        second = random.randint(0, 59)

        timestamp = day.replace(
            hour=hour,
            minute=minute,
            second=second
        )

        # Never generate commits outside requested range.
        if timestamp < START:
            continue

        if timestamp > END:
            continue

        timestamps.append(timestamp)

    return sorted(timestamps)


def choose_commit_count():
    """
    Choose a normal-day commit count.
    """

    return random.choices(
        NORMAL_COUNTS,
        weights=NORMAL_WEIGHTS
    )[0]


def commit_to_git(timestamp):
    """
    Create one Git commit with a historical timestamp.
    """

    stamp = (
        timestamp.strftime("%Y-%m-%dT%H:%M:%S")
        + TIMEZONE
    )

    with open(
        ACTIVITY_FILE,
        "a",
        encoding="utf-8"
    ) as file:

        file.write(
            f"Synthetic research activity: {stamp}\n"
        )

    subprocess.run(
        ["git", "add", ACTIVITY_FILE],
        check=True
    )

    environment = {
        **os.environ,
        "GIT_AUTHOR_DATE": stamp,
        "GIT_COMMITTER_DATE": stamp,
    }

    subprocess.run(
        [
            "git",
            "commit",
            "-q",
            "-m",
            "Research: synthetic activity"
        ],
        env=environment,
        check=True
    )


# ============================================================
# MAIN SIMULATION
# ============================================================

def main():

    print()
    print("=" * 60)
    print("GitHub Contribution Graph Research Experiment")
    print("=" * 60)
    print()

    print(f"Start date : {START.date()}")
    print(f"End date   : {END.date()}")
    print(f"Seed       : {SEED}")
    print(f"Dry run    : {DRY_RUN}")
    print()

    breaks = build_breaks(
        START,
        END
    )

    year_rates = build_year_rates(
        START,
        END
    )

    month_multipliers = build_month_multipliers(
        START,
        END
    )

    commits_per_year = defaultdict(int)
    active_days_per_year = defaultdict(int)
    weekend_active_days = 0
    weekday_active_days = 0

    commit_count_distribution = Counter()

    spike_days = 0
    total_commits = 0

    day = START.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0
    )

    while day <= END:

        # ----------------------------------------------------
        # Skip break/vacation days
        # ----------------------------------------------------

        if day.date() in breaks:

            day += timedelta(days=1)
            continue

        # ----------------------------------------------------
        # Determine base activity probability
        # ----------------------------------------------------

        weekday_probability, weekend_probability = (
            year_rates[day.year]
        )

        if day.weekday() >= 5:
            base_probability = weekend_probability
        else:
            base_probability = weekday_probability

        # ----------------------------------------------------
        # Apply monthly variation
        # ----------------------------------------------------

        monthly_multiplier = month_multipliers[
            (day.year, day.month)
        ]

        probability = (
            base_probability *
            monthly_multiplier
        )

        probability = min(
            probability,
            0.95
        )

        # ----------------------------------------------------
        # Decide whether this is an active day
        # ----------------------------------------------------

        if random.random() < probability:

            # ------------------------------------------------
            # Spike day?
            # ------------------------------------------------

            if random.random() < SPIKE_PROB:

                number_of_commits = random.randint(
                    *SPIKE_RANGE
                )

                spike_days += 1

            else:

                number_of_commits = (
                    choose_commit_count()
                )

            # ------------------------------------------------
            # Generate timestamps
            # ------------------------------------------------

            timestamps = generate_commit_times(
                day,
                number_of_commits
            )

            # ------------------------------------------------
            # Record statistics
            # ------------------------------------------------

            actual_count = len(timestamps)

            if actual_count == 0:
                day += timedelta(days=1)
                continue

            commit_count_distribution[
                actual_count
            ] += 1

            active_days_per_year[
                day.year
            ] += 1

            if day.weekday() >= 5:
                weekend_active_days += 1
            else:
                weekday_active_days += 1

            # ------------------------------------------------
            # Create commits
            # ------------------------------------------------

            for timestamp in timestamps:

                total_commits += 1

                if total_commits > MAX_TOTAL_COMMITS:

                    raise RuntimeError(
                        "Maximum commit safety limit reached."
                    )

                commits_per_year[
                    timestamp.year
                ] += 1

                if not DRY_RUN:
                    commit_to_git(timestamp)

        day += timedelta(days=1)

    # ========================================================
    # STATISTICS
    # ========================================================

    print("-" * 60)
    print("RESULTS")
    print("-" * 60)

    print()

    print("Commits per calendar year:")

    for year in sorted(commits_per_year):

        print(
            f"  {year}: "
            f"{commits_per_year[year]:5d} commits | "
            f"{active_days_per_year[year]:4d} active days"
        )

    print()

    print(f"Total commits : {total_commits}")
    print(f"Spike days    : {spike_days}")
    print(f"Break dates   : {len(breaks)}")
    print()

    print("Normal commit-count distribution:")

    for count in sorted(commit_count_distribution):

        days = commit_count_distribution[count]

        print(
            f"  {count:2d} commits/day : "
            f"{days:4d} active days"
        )

    print()

    print(
        f"Weekday active days : "
        f"{weekday_active_days}"
    )

    print(
        f"Weekend active days : "
        f"{weekend_active_days}"
    )

    print()

    if DRY_RUN:

        print(
            "DRY RUN: No Git commits were created."
        )

    else:

        print(
            "Synthetic Git history generated."
        )

    print()
    print("=" * 60)


if __name__ == "__main__":
    main()