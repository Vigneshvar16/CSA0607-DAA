#!/usr/bin/env python3
"""
student_search_analysis.py
==========================
CO1 Assignment - Searching student registration numbers.

This ONE file contains everything needed for the experimental part of the
assignment:

    * Linear search, iterative binary search, recursive binary search
      (each returns (index, key_comparisons); index is -1 when not found)
    * Unit tests (first / middle / last / missing / empty / single / invalid)
    * Validation of the theoretical comparison-count formulas against the code
    * Benchmarks for n = 1,000 / 10,000 / 100,000 / 1,000,000 records
    * CSV export (opens in Excel) and graph generation (matplotlib, optional)
    * A concise terminal summary

Run:   python student_search_analysis.py
Needs: Python 3.8+ (standard library only).  matplotlib is OPTIONAL (graphs).

All data are SYNTHETIC and generated deterministically (fixed seed).  They are
meant for testing algorithm behaviour only; they do not model real students.

Basic operation (counted): one key comparison between the target registration
number and a stored registration number.
  * Linear search           : one "==" test per element examined.
  * Binary search (both)    : one three-way comparison (equal / less / greater)
                              of the target with data[mid] per probe.
"""

import bisect
import csv
import math
import platform
import random
import sys
import time
from datetime import datetime
from pathlib import Path

# --------------------------------------------------------------------------
# Configuration (all documented assumptions live here)
# --------------------------------------------------------------------------
SEED = 20240607                      # fixed seed -> reproducible data
BASE = 2_000_000_000                 # synthetic 10-digit registration numbers
SIZES = [1_000, 10_000, 100_000, 1_000_000]
# Number of successful AND of unsuccessful queries in the "representative
# query set" (smaller for large n so that linear search stays affordable).
QUERIES_PER_KIND = {1_000: 200, 10_000: 200, 100_000: 100, 1_000_000: 50}
DAILY_BATCH = 1_000                  # assumed number of new records per day
REQUESTS_PER_HOUR = 50_000           # from the problem statement
PEAK_FACTOR = 10                     # assumed peak-to-average load ratio

SCRIPT_DIR = Path(__file__).resolve().parent
if SCRIPT_DIR.name == "Source_Code" and SCRIPT_DIR.parent.name == "Task_8_Implementation_Testing":
    ROOT_DIR = SCRIPT_DIR.parents[1]                 # .../CO1_Assignment
else:                                                # script moved elsewhere
    ROOT_DIR = SCRIPT_DIR / "CO1_Assignment"
OUT_DIR = ROOT_DIR / "Report" / "Tables_and_Graphs"


# --------------------------------------------------------------------------
# The three algorithms
# --------------------------------------------------------------------------
def _validate(data, target):
    """O(1) input validation (types only; sortedness is NOT checked here
    because checking it would cost O(n) and destroy binary search's benefit)."""
    if not isinstance(data, (list, tuple)):
        raise TypeError("data must be a list or tuple of integer registration numbers")
    if isinstance(target, bool) or not isinstance(target, int):
        raise TypeError("target registration number must be an integer")


def linear_search(data, target):
    """Linear search on an (un)sorted sequence. Returns (index or -1, comparisons)."""
    _validate(data, target)
    comparisons = 0
    for index, value in enumerate(data):
        comparisons += 1                      # key comparison: value == target
        if value == target:
            return index, comparisons
    return -1, comparisons


def iterative_binary_search(data, target):
    """Iterative binary search. PRECONDITION: data sorted ascending.
    Returns (index or -1, comparisons)."""
    _validate(data, target)
    low, high = 0, len(data) - 1
    comparisons = 0
    while low <= high:
        mid = (low + high) // 2
        comparisons += 1                      # one three-way key comparison
        value = data[mid]
        if value == target:
            return mid, comparisons
        if value < target:
            low = mid + 1
        else:
            high = mid - 1
    return -1, comparisons


def _rbs(data, target, low, high, stats, depth):
    """Recursive worker. stats = [comparisons, max_stack_frames]."""
    if depth > stats[1]:
        stats[1] = depth
    if low > high:                            # empty sub-array: base case, not found
        return -1
    mid = (low + high) // 2
    stats[0] += 1                             # one three-way key comparison
    value = data[mid]
    if value == target:
        return mid
    if value < target:
        return _rbs(data, target, mid + 1, high, stats, depth + 1)
    return _rbs(data, target, low, mid - 1, stats, depth + 1)


def recursive_binary_search(data, target, stats=None):
    """Recursive binary search. PRECONDITION: data sorted ascending.
    Returns (index or -1, comparisons).  If a list `stats` ([0, 0]) is passed,
    stats[1] receives the maximum number of simultaneous stack frames."""
    _validate(data, target)
    if stats is None:
        stats = [0, 0]
    index = _rbs(data, target, 0, len(data) - 1, stats, 1)
    return index, stats[0]


ALGORITHMS = [
    ("Linear Search", linear_search),
    ("Iterative Binary Search", iterative_binary_search),
    ("Recursive Binary Search", recursive_binary_search),
]


def is_strictly_sorted(data):
    return all(data[i] < data[i + 1] for i in range(len(data) - 1))


# --------------------------------------------------------------------------
# Theoretical comparison counts for the algorithms as implemented above
# --------------------------------------------------------------------------
def bin_height(n):
    """Maximum comparisons of a successful binary search: floor(log2 n) + 1."""
    return n.bit_length() if n > 0 else 0


def bin_avg_successful(n):
    """Exact average comparisons over all n stored keys (uniform).
    The probe tree has full levels 1..h-1 and a partly filled last level."""
    h = bin_height(n)
    total = sum(j * (1 << (j - 1)) for j in range(1, h)) + h * (n - ((1 << (h - 1)) - 1))
    return total / n


def bin_avg_unsuccessful(n):
    """Exact average comparisons over all n+1 gaps (uniform)."""
    h = bin_height(n)
    at_h = 2 * (n - (1 << (h - 1)) + 1)       # gaps needing h comparisons
    return (h * at_h + (h - 1) * (n + 1 - at_h)) / (n + 1)


# --------------------------------------------------------------------------
# Unit tests
# --------------------------------------------------------------------------
def run_unit_tests():
    S = [2000000101, 2000000250, 2000000377, 2000000480, 2000000615, 2000000733, 2000000890]
    E4 = [2000000010, 2000000020, 2000000030, 2000000040]
    normal = [
        ("T1", "First element", "sorted list, n=7", S, S[0], 0),
        ("T2", "Middle element", "sorted list, n=7", S, S[3], 3),
        ("T3", "Last element", "sorted list, n=7", S, S[6], 6),
        ("T4", "Missing number between two stored numbers", "sorted list, n=7", S, 2000000500, -1),
        ("T5", "Missing number smaller than all", "sorted list, n=7", S, 2000000001, -1),
        ("T6", "Missing number larger than all", "sorted list, n=7", S, 2000000999, -1),
        ("T7", "Empty list", "empty list, n=0", [], 2000000101, -1),
        ("T8", "Single-element list, key present", "n=1", [2000000555], 2000000555, 0),
        ("T9", "Single-element list, key absent", "n=1", [2000000555], 2000000556, -1),
        ("T10", "Even-length list, second element", "sorted list, n=4", E4, E4[1], 1),
        ("T11", "Even-length list, last element", "sorted list, n=4", E4, E4[3], 3),
    ]
    rows = []
    for tid, desc, kind, data, target, expected in normal:
        assert is_strictly_sorted(data)       # binary search precondition
        res = [func(data, target) for _, func in ALGORITHMS]
        ok = all(r[0] == expected for r in res)
        rows.append([tid, desc, kind, target, str(expected), "/".join(str(r[0]) for r in res),
                     "/".join(str(r[1]) for r in res), "PASS" if ok else "FAIL"])

    # T12: UNSORTED input. Linear search runs on the original list; binary
    # searches run only on a sorted COPY (never on unsorted data).
    U = [2000000615, 2000000101, 2000000890, 2000000377, 2000000250]
    target = 2000000377
    SU = sorted(U)
    assert is_strictly_sorted(SU)
    li, lc = linear_search(U, target)
    ii, ic = iterative_binary_search(SU, target)
    ri, rc = recursive_binary_search(SU, target)
    ok = (li == 3 and ii == 2 and ri == 2 and U[li] == SU[ii] == SU[ri] == target)
    rows.append(["T12", "Unsorted list: linear on original, binary on sorted copy",
                 "unsorted list, n=5", target, "3 / 2 / 2 (same key found)",
                 f"{li}/{ii}/{ri}", f"{lc}/{ic}/{rc}", "PASS" if ok else "FAIL"])

    # T13-T16: invalid inputs must raise TypeError in all three algorithms.
    invalid = [
        ("T13", "Invalid target: string", S, "2000000101"),
        ("T14", "Invalid target: float", S, 2000000101.0),
        ("T15", "Invalid target: bool", S, True),
        ("T16", "Invalid data: None instead of a list", None, 2000000101),
    ]
    for tid, desc, data, target in invalid:
        raised = []
        for _, func in ALGORITHMS:
            try:
                func(data, target)
                raised.append("no error")
            except TypeError:
                raised.append("TypeError")
        ok = all(r == "TypeError" for r in raised)
        rows.append([tid, desc, "invalid input", repr(target), "TypeError (all three)",
                     "/".join(raised), "-", "PASS" if ok else "FAIL"])
    return rows


# --------------------------------------------------------------------------
# Validation of theoretical formulas (exhaustive over every key and every gap)
# --------------------------------------------------------------------------
def _exhaustive(func, n):
    """Run every successful key and every unsuccessful gap on data of size n."""
    data = [BASE + 2 * i for i in range(n)]          # even offsets -> odd gaps
    succ, gaps, depth = [], [], 0
    is_rec = func is recursive_binary_search
    for i in range(n):
        st = [0, 0]
        idx, c = func(data, BASE + 2 * i, st) if is_rec else func(data, BASE + 2 * i)
        assert idx == i
        succ.append(c)
        depth = max(depth, st[1])
    for i in range(n + 1):
        st = [0, 0]
        idx, c = func(data, BASE + 2 * i - 1, st) if is_rec else func(data, BASE + 2 * i - 1)
        assert idx == -1
        gaps.append(c)
        depth = max(depth, st[1])
    return succ, gaps, depth


def validate_theory():
    rows = []

    def add(alg, n, case, formula, theory, measured):
        match = abs(theory - measured) < 1e-9
        rows.append([alg, n, case, formula, round(theory, 6), round(measured, 6),
                     "yes" if match else "NO"])

    for n in [1, 2, 10, 100, 1000]:
        succ, gaps, _ = _exhaustive(linear_search, n)
        add("Linear Search", n, "best successful", "1", 1, min(succ))
        add("Linear Search", n, "worst successful", "n", n, max(succ))
        add("Linear Search", n, "average successful", "(n+1)/2", (n + 1) / 2, sum(succ) / n)
        add("Linear Search", n, "worst unsuccessful", "n", n, max(gaps))
        add("Linear Search", n, "average unsuccessful", "n", n, sum(gaps) / (n + 1))

    for name, func in ALGORITHMS[1:]:
        for n in [1, 2, 3, 7, 8, 15, 100, 1000, 1023, 10000, 100000]:
            succ, gaps, depth = _exhaustive(func, n)
            h = bin_height(n)
            add(name, n, "best successful", "1", 1, min(succ))
            add(name, n, "worst successful", "floor(log2 n)+1", h, max(succ))
            add(name, n, "average successful", "exact probe-tree sum / n",
                bin_avg_successful(n), sum(succ) / n)
            add(name, n, "worst unsuccessful", "floor(log2 n)+1", h, max(gaps))
            add(name, n, "average unsuccessful", "exact gap formula",
                bin_avg_unsuccessful(n), sum(gaps) / (n + 1))
            if func is recursive_binary_search:
                add(name, n, "max stack frames", "floor(log2 n)+2", h + 1, depth)
    return rows


# --------------------------------------------------------------------------
# Benchmark helpers
# --------------------------------------------------------------------------
def time_search(func, data, target, repeats, trials=3):
    """Mean time of one search over `repeats` runs; the BEST (minimum) of
    `trials` such trials is returned to reduce operating-system noise."""
    best = float("inf")
    for _ in range(trials):
        t0 = time.perf_counter()
        for _ in range(repeats):
            func(data, target)
        best = min(best, (time.perf_counter() - t0) / repeats)
    return best


def time_query_set(func, data, queries, repeats, trials=3):
    """Mean time per query over the query set; best of `trials` trials."""
    best = float("inf")
    for _ in range(trials):
        t0 = time.perf_counter()
        for _ in range(repeats):
            for q in queries:
                func(data, q)
        best = min(best, (time.perf_counter() - t0) / (repeats * len(queries)))
    return best


def make_scenarios(sorted_data, present):
    n = len(sorted_data)
    absent = sorted_data[n // 3] + 1                  # an absent key inside the range
    while absent in present:
        absent += 1
    return [
        ("successful - near beginning", sorted_data[n // 100], n // 100),
        ("successful - middle", sorted_data[n // 2], n // 2),
        ("successful - near end", sorted_data[n - 1 - n // 100], n - 1 - n // 100),
        ("unsuccessful", absent, -1),
    ]


def run_benchmarks():
    scen_rows, query_rows, pre_rows = [], [], []
    consistency_checks = 0
    consistency_ok = True

    for n in SIZES:
        rnd = random.Random(SEED + n)
        unsorted = rnd.sample(range(BASE, BASE + 10 * n), n)      # unique, unsorted
        # Re-create the int objects in list order so that every dataset size has
        # the same memory layout (random.sample allocates them in a size-dependent
        # order, which would otherwise add a cache-miss artefact for some n).
        unsorted = [x + 0 for x in unsorted]
        # --- preprocessing: sorting a copy, building a hash set (supplementary)
        reps = 5 if n <= 100_000 else 3
        t0 = time.perf_counter()
        for _ in range(reps):
            sorted_copy = sorted(unsorted)
        sort_time = (time.perf_counter() - t0) / reps
        sorted_copy = [x + 0 for x in sorted_copy]    # same sequential layout as `unsorted`
        assert is_strictly_sorted(sorted_copy)       # binary search precondition
        t0 = time.perf_counter()
        for _ in range(reps):
            present = set(unsorted)
        set_time = (time.perf_counter() - t0) / reps

        # --- scenario experiments: all algorithms on the SAME sorted list
        for scen, key, exp_idx in make_scenarios(sorted_copy, present):
            results = []
            for name, func in ALGORITHMS:
                idx, comps = func(sorted_copy, key)
                results.append((name, func, idx, comps))
            consistency_checks += 1
            if len({r[2] for r in results}) != 1 or results[0][2] != exp_idx:
                consistency_ok = False
            for name, func, idx, comps in results:
                if name == "Linear Search":
                    repeats = max(1, min(2000, 1_000_000 // comps))
                    bound = comps if exp_idx == -1 else exp_idx + 1
                else:
                    repeats = 20_000
                    bound = bin_height(n)
                t = time_search(func, sorted_copy, key, repeats)
                scen_rows.append([n, name, scen, key, "yes" if idx >= 0 else "no", idx,
                                  comps, bound, round(t * 1e6, 4), repeats])

        # --- representative query set: successful + unsuccessful, shuffled
        k = QUERIES_PER_KIND[n]
        hits = rnd.sample(unsorted, k)
        misses = []
        while len(misses) < k:
            c = rnd.randrange(BASE, BASE + 10 * n)
            if c not in present:
                misses.append(c)
        queries = hits + misses
        rnd.shuffle(queries)
        for name, func in ALGORITHMS:
            data = unsorted if name == "Linear Search" else sorted_copy
            c_hit = c_miss = n_hit = n_miss = depth = 0
            for q in queries:
                st = [0, 0]
                idx, comps = func(data, q, st) if func is recursive_binary_search else func(data, q)
                found = idx >= 0
                consistency_checks += 1
                if found != (q in present) or (found and data[idx] != q):
                    consistency_ok = False
                if found:
                    c_hit += comps
                    n_hit += 1
                else:
                    c_miss += comps
                    n_miss += 1
                depth = max(depth, st[1])
            if name == "Linear Search":
                repeats = max(1, min(10, int(5e6 // (0.75 * n * len(queries)))))
                th_s, th_u = (n + 1) / 2, float(n)
            else:
                repeats = 20 if n <= 100_000 else 5
                th_s, th_u = bin_avg_successful(n), bin_avg_unsuccessful(n)
            t = time_query_set(func, data, queries, repeats, trials=2 if n >= 1_000_000 else 3)
            query_rows.append([
                n, name, "unsorted" if name == "Linear Search" else "sorted",
                n_hit, n_miss, round(c_hit / n_hit, 3), round(c_miss / n_miss, 3),
                round((c_hit + c_miss) / len(queries), 3), round(th_s, 3), round(th_u, 3),
                round(t * 1e6, 4), repeats, depth if func is recursive_binary_search else ""])

        # --- supplementary: daily-update cost and hash-set lookup cost
        rnd2 = random.Random(SEED + 7 * n)
        batch = []
        while len(batch) < DAILY_BATCH:
            c = rnd2.randrange(BASE, BASE + 10 * n)
            if c not in present:
                batch.append(c)
        reps2 = 3
        t0 = time.perf_counter()
        for _ in range(reps2):
            merged = sorted_copy + batch
            merged.sort()
        resort = (time.perf_counter() - t0) / reps2
        t0 = time.perf_counter()
        for _ in range(reps2):
            merged = list(sorted_copy)
            for key in batch:
                bisect.insort(merged, key)
        insort = (time.perf_counter() - t0) / reps2
        t0 = time.perf_counter()
        for _ in range(20):
            for q in queries:
                _ = q in present
        lookup = (time.perf_counter() - t0) / (20 * len(queries))
        pre_rows.append([n, round(sort_time, 6), round(resort, 6), round(insort, 6),
                         round(set_time, 6), round(lookup * 1e6, 4)])

    return scen_rows, query_rows, pre_rows, consistency_checks, consistency_ok


def system_estimates(query_rows, pre_rows):
    """Back-of-the-envelope load estimates for n = 1,000,000 using MEASURED
    per-query times (single-threaded CPython microbenchmark, not a service test)."""
    n = SIZES[-1]
    rate = REQUESTS_PER_HOUR / 3600.0
    peak = rate * PEAK_FACTOR
    t = {r[1]: r[10] for r in query_rows if r[0] == n}          # us per query
    pre = [r for r in pre_rows if r[0] == n][0]
    sort_s, resort_s, insort_s, set_s, lookup_us = pre[1], pre[2], pre[3], pre[4], pre[5]
    rows = [
        ["requests per hour", REQUESTS_PER_HOUR, "req/h", "given in the problem statement"],
        ["average request rate", round(rate, 4), "req/s", "50,000 / 3,600"],
        ["assumed peak factor", PEAK_FACTOR, "x", "ASSUMPTION (not given in the brief)"],
        ["assumed peak request rate", round(peak, 3), "req/s", "average rate x peak factor"],
    ]
    for name, _ in ALGORITHMS:
        us = t[name]
        rows.append([f"{name}: measured time per query (n=1,000,000)", us, "us", "mixed 50%/50% hit/miss query set"])
        rows.append([f"{name}: single-core busy fraction at average rate",
                     round(rate * us * 1e-6, 8), "fraction", "rate x time per query"])
        rows.append([f"{name}: single-core busy fraction at assumed peak rate",
                     round(peak * us * 1e-6, 8), "fraction", "peak rate x time per query"])
        rows.append([f"{name}: CPU-seconds needed per hour of traffic",
                     round(REQUESTS_PER_HOUR * us * 1e-6, 6), "s", "50,000 x time per query"])
    rows += [
        ["one-time sort of 1,000,000 keys", sort_s, "s", "measured (sorted copy)"],
        ["break-even number of queries: sort once + binary vs linear",
         round(sort_s / ((t["Linear Search"] - t["Iterative Binary Search"]) * 1e-6), 2), "queries",
         "sort_time / (t_linear - t_binary)"],
        ["CPU-seconds per hour if the data were re-sorted for EVERY query",
         round(REQUESTS_PER_HOUR * sort_s, 2), "s", "50,000 x sort time (strawman, shows why not to do it)"],
        [f"daily update: append {DAILY_BATCH} keys then re-sort list", resort_s, "s", "measured"],
        [f"daily update: bisect.insort {DAILY_BATCH} keys one by one", insort_s, "s", "measured"],
        ["supplementary: build a hash set of 1,000,000 keys", set_s, "s", "measured"],
        ["supplementary: hash-set membership test", lookup_us, "us", "measured (not one of the three required algorithms)"],
    ]
    return rows


# --------------------------------------------------------------------------
# Output helpers
# --------------------------------------------------------------------------
def write_csv(name, header, rows):
    path = OUT_DIR / name
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    return path


def make_graphs(scen_rows, query_rows):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("NOTE: matplotlib is not installed -> graphs skipped "
              "(install with: pip install matplotlib). Tables and CSV files are still produced.")
        return []
    style = {"Linear Search": ("o-", "tab:red"),
             "Iterative Binary Search": ("s-", "tab:blue"),
             "Recursive Binary Search": ("x--", "tab:green")}
    paths = []

    # ---- Graph 1: comparison counts
    fig, ax = plt.subplots(1, 2, figsize=(12, 4.8))
    for name, _ in ALGORITHMS:
        pts = [(r[0], r[6]) for r in scen_rows if r[1] == name and r[2] == "unsuccessful"]
        ax[0].plot(*zip(*pts), style[name][0], color=style[name][1], label=name, markersize=8)
        pts = [(r[0], r[7]) for r in query_rows if r[1] == name]
        ax[1].plot(*zip(*pts), style[name][0], color=style[name][1], label=name, markersize=8)
    ax[0].plot(SIZES, SIZES, ":", color="gray", label="theory: n")
    ax[0].plot(SIZES, [bin_height(n) for n in SIZES], ":", color="black", label="theory: floor(log2 n)+1")
    ax[0].set_title("Worst case (unsuccessful search): comparisons")
    ax[1].set_title("Representative query set: average comparisons per query")
    for a in ax:
        a.set_xscale("log"); a.set_yscale("log")
        a.set_xlabel("Number of records n (log scale)")
        a.set_ylabel("Key comparisons (log scale)")
        a.grid(True, which="both", alpha=0.3); a.legend(fontsize=8)
    fig.suptitle("Comparison counts by dataset size", fontsize=13)
    fig.tight_layout()
    p = OUT_DIR / "comparison_counts_by_size.png"
    fig.savefig(p, dpi=150); plt.close(fig); paths.append(p)

    # ---- Graph 2: execution time
    fig, ax = plt.subplots(1, 2, figsize=(12, 4.8))
    for name, _ in ALGORITHMS:
        pts = [(r[0], r[8]) for r in scen_rows if r[1] == name and r[2] == "unsuccessful"]
        ax[0].plot(*zip(*pts), style[name][0], color=style[name][1], label=name, markersize=8)
        pts = [(r[0], r[10]) for r in query_rows if r[1] == name]
        ax[1].plot(*zip(*pts), style[name][0], color=style[name][1], label=name, markersize=8)
    ax[0].set_title("Single unsuccessful search: time per search")
    ax[1].set_title("Representative query set: average time per query")
    for a in ax:
        a.set_xscale("log"); a.set_yscale("log")
        a.set_xlabel("Number of records n (log scale)")
        a.set_ylabel("Time in microseconds (log scale)")
        a.grid(True, which="both", alpha=0.3); a.legend(fontsize=8)
    fig.suptitle("Execution time by dataset size (CPython, time.perf_counter)", fontsize=13)
    fig.tight_layout()
    p = OUT_DIR / "execution_time_by_size.png"
    fig.savefig(p, dpi=150); plt.close(fig); paths.append(p)
    return paths


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    print("=" * 74)
    print("Student Registration Number Search - analysis of three algorithms")
    print(f"Python {platform.python_version()} on {platform.system()} | seed {SEED} | synthetic data")
    print("=" * 74)

    # 1. unit tests
    tests = run_unit_tests()
    passed = sum(1 for r in tests if r[-1] == "PASS")
    write_csv("test_cases.csv",
              ["id", "description", "input", "target", "expected", "actual (linear/iterative/recursive)",
               "comparisons (L/I/R)", "status"], tests)
    print(f"[1] Unit tests: {passed}/{len(tests)} passed")
    for r in tests:
        if r[-1] != "PASS":
            print("    FAILED:", r[0], r[1])

    # 2. theory validation
    theory = validate_theory()
    ok_theory = sum(1 for r in theory if r[-1] == "yes")
    write_csv("theory_validation.csv",
              ["algorithm", "n", "case", "theoretical_formula", "theoretical_value",
               "measured_value", "match"], theory)
    print(f"[2] Theory vs code (exhaustive counts): {ok_theory}/{len(theory)} formula checks matched")

    # 3. benchmarks
    print(f"[3] Benchmarking n = {', '.join(f'{n:,}' for n in SIZES)} (a few seconds to ~1 minute) ...")
    scen, query, pre, n_checks, consistent = run_benchmarks()
    print(f"    Result consistency across the 3 algorithms: "
          f"{'OK' if consistent else 'MISMATCH'} ({n_checks} cross-checks)")
    write_csv("benchmark_scenarios.csv",
              ["n", "algorithm", "scenario", "target_key", "found", "index", "comparisons",
               "theory_comparisons_or_bound", "time_per_search_us_best_of_3", "timing_repeats"], scen)
    write_csv("benchmark_query_sets.csv",
              ["n", "algorithm", "data_order", "successful_queries", "unsuccessful_queries",
               "avg_comparisons_successful", "avg_comparisons_unsuccessful", "avg_comparisons_overall",
               "theory_avg_successful", "theory_avg_unsuccessful", "avg_time_per_query_us_best_of_trials",
               "timing_repeats", "max_stack_frames_recursive"], query)
    write_csv("preprocessing_costs.csv",
              ["n", "sort_time_s", f"append_{DAILY_BATCH}_and_resort_s", f"insort_{DAILY_BATCH}_keys_s",
               "hash_set_build_s", "hash_set_lookup_us"], pre)
    est = system_estimates(query, pre)
    write_csv("system_estimates.csv", ["item", "value", "unit", "basis"], est)
    write_csv("run_metadata.csv", ["item", "value"], [
        ["generated_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
        ["python_version", platform.python_version()], ["platform", platform.platform()],
        ["processor", platform.processor() or "n/a"], ["seed", SEED],
        ["dataset_sizes", " ".join(str(n) for n in SIZES)],
        ["queries_per_kind(n=1000/10000/100000/1000000)",
         "/".join(str(QUERIES_PER_KIND[n]) for n in SIZES)],
        ["daily_batch_assumed", DAILY_BATCH], ["peak_factor_assumed", PEAK_FACTOR]])

    # terminal summary
    print("\nWorst case = unsuccessful search; comparisons counted by the code:")
    print(f"{'n':>10} | {'Linear':>9} | {'Iterative':>9} | {'Recursive':>9} | {'theory n':>9} | {'floor(log2 n)+1':>15}")
    for n in SIZES:
        c = {r[1]: r[6] for r in scen if r[0] == n and r[2] == "unsuccessful"}
        print(f"{n:>10,} | {c['Linear Search']:>9,} | {c['Iterative Binary Search']:>9} | "
              f"{c['Recursive Binary Search']:>9} | {n:>9,} | {bin_height(n):>15}")
    print("\nAverage time per query on the representative query set (microseconds):")
    print(f"{'n':>10} | {'Linear':>12} | {'Iterative':>10} | {'Recursive':>10}")
    for n in SIZES:
        t = {r[1]: r[10] for r in query if r[0] == n}
        print(f"{n:>10,} | {t['Linear Search']:>12.2f} | {t['Iterative Binary Search']:>10.2f} | "
              f"{t['Recursive Binary Search']:>10.2f}")
    sort_1m = [r for r in pre if r[0] == SIZES[-1]][0][1]
    rate = REQUESTS_PER_HOUR / 3600
    print(f"\nLoad: {REQUESTS_PER_HOUR:,} requests/hour = {rate:.2f} requests/second on average.")
    print(f"Sorting 1,000,000 keys once takes about {sort_1m:.2f} s (preprocessing, paid once per update).")

    figures = make_graphs(scen, query)

    all_ok = passed == len(tests) and ok_theory == len(theory) and consistent
    print("\nRECOMMENDATION: iterative binary search on a sorted array (rebuild/merge once per day).")
    print("  Reason: ~20 comparisons per lookup at n = 1,000,000 versus up to 1,000,000 for linear search;")
    print("  no recursion-stack overhead. In production a hash index / database index is also worth considering.")
    print("\nFiles written to:", OUT_DIR)
    for p in sorted(OUT_DIR.glob("*.csv")) + figures:
        print("  -", p.name)
    print(f"\nOVERALL: {'ALL CHECKS PASSED' if all_ok else 'SOME CHECKS FAILED'} "
          f"(runtime {time.perf_counter() - started:.1f} s)")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
