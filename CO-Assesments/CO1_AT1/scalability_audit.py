"""ShopSphere Scalability Audit - CSA06 DAA, CO1 Assessment Tool 1.

Standard library only.  Run:  python scalability_audit.py

Result labels used in the output and comments:
  [exact]      closed-form count, verified against loop-level simulation
  [asymptotic] Theta-class from the derivations in the report
  [model]      illustrative recurrence estimate (NOT a measured runtime)

Declared recurrence cost model (M4, M5):
  T(m) = a*T(m // 2) + f(m),  T(1) = 1,  one unit of f = one basic operation.
  M5 uses f(m) = m * floor(log2 m), computed with integer bit_length().
"""
from fractions import Fraction
from functools import lru_cache
from math import log2

N_FUTURE = 1_000_000      # expected catalogue size
RATE = 10**8              # basic operations per second
WINDOW = 600              # 10-minute nightly window, in seconds


# ---------------------------------------------------------------- exact counts
def m1_comparisons(n):
    """M1: sum_{i=0}^{n-2} (n-i-1) = n(n-1)/2 pairwise comparisons."""
    return n * (n - 1) // 2


def m2_audits(n):
    """M2: 1+2+...+2^k with 2^k < n  ->  2^ceil(log2 n) - 1  (n >= 1)."""
    return (1 << (n - 1).bit_length()) - 1


def m2_simulated(n):
    """Loop-level simulation of M2: add the inner-loop size i per round."""
    i, total = 1, 0
    while i < n:
        total += i
        i *= 2
    return total


def s2_comparisons(n):
    """S2: T(n) = T(n//2) + 1, T(1) = 1  ->  floor(log2 n) + 1."""
    @lru_cache(maxsize=None)
    def t(m):
        return 1 if m <= 1 else t(m // 2) + 1
    return t(n)


def s1_expected(n, p):
    """S1: E[C] = p(n+1)/2 + (1-p)n  (exact rational arithmetic)."""
    p = Fraction(p)
    return p * Fraction(n + 1, 2) + (1 - p) * n


# ------------------------------------------------- recurrence cost model [model]
def recurrence_cost(a, f, n):
    """Evaluate T(m) = a*T(m//2) + f(m), T(1) = 1 with memoisation."""
    @lru_cache(maxsize=None)
    def t(m):
        return 1 if m <= 1 else a * t(m // 2) + f(m)
    return t(n)


def f_linear(m):
    return m


def f_nlogn(m):
    return m * (m.bit_length() - 1)      # m * floor(log2 m)


def report_generator_ops(n):
    """f(n) = 3n^2 + 10 n log2(n) + 50, treated as an operation count."""
    return round(3 * n * n + 10 * n * log2(n) + 50)


def seconds(ops):
    return ops / RATE


def verdict(sec):
    return "fits" if sec <= WINDOW else "EXCEEDS"


# --------------------------------------------------------------------- checks
def binary_search_probes(arr, key):
    """Instrumented binary search: one three-way key comparison per probe."""
    lo, hi, probes = 0, len(arr) - 1, 0
    while lo <= hi:
        mid = (lo + hi) // 2
        probes += 1
        if arr[mid] == key:
            break
        lo, hi = (mid + 1, hi) if arr[mid] < key else (lo, mid - 1)
    return probes


def run_checks():
    ok = []
    # M1: formula vs explicit double sum and literal pair count
    ok.append(all(m1_comparisons(n) == sum(n - i - 1 for i in range(n - 1))
                  == sum(1 for i in range(n) for j in range(i + 1, n))
                  for n in range(1, 60)))
    ok.append(m1_comparisons(N_FUTURE) == sum(N_FUTURE - i - 1 for i in range(N_FUTURE - 1)))
    # M2: closed form vs simulation, literal Audit loop, bounds n-1 <= A <= 2n-3
    def literal(n):
        c, i = 0, 1
        while i < n:
            c += sum(1 for _ in range(i))
            i *= 2
        return c
    ok.append(all(m2_audits(n) == m2_simulated(n) for n in range(1, 5000)))
    ok.append(all(m2_audits(n) == literal(n) for n in range(1, 300)))
    ok.append(all(n - 1 <= m2_audits(n) <= 2 * n - 3 for n in range(2, 5000)))
    ok.append(m2_audits(1024) == 1023 == sum(2**t for t in range(10)))
    ok.append(m2_audits(N_FUTURE) == 2**20 - 1 == m2_simulated(N_FUTURE))
    # S2: recurrence vs floor(log2 n)+1 vs instrumented binary search worst case
    ok.append(all(s2_comparisons(n) == n.bit_length() for n in range(1, 5000)))
    ok.append(all(s2_comparisons(2**k) == k + 1 for k in range(21)))
    worst = lambda n: max(binary_search_probes(list(range(0, 2 * n, 2)), key)
                          for key in range(-1, 2 * n + 1))
    ok.append(all(worst(n) == s2_comparisons(n) for n in range(1, 130)))
    # S1: simplified form n - p(n-1)/2 and brute-force average over positions
    ok.append(s1_expected(N_FUTURE, Fraction(1, 2)) == Fraction(3000001, 4))
    ok.append(all(s1_expected(n, Fraction(1, 3))
                  == Fraction(1, 3) * Fraction(sum(range(1, n + 1)), n)
                  + Fraction(2, 3) * n == n - Fraction(1, 3) * Fraction(n - 1, 2)
                  for n in range(1, 50)))
    # M4 / M5: recurrence model vs closed forms at n = 2^k
    for k in range(1, 21):
        n = 2**k
        ok.append(recurrence_cost(4, f_linear, n) == 2 * n * n - n)
        ok.append(recurrence_cost(2, f_linear, n) == n * k + n)
        ok.append(recurrence_cost(2, f_nlogn, n) == n * (k * (k + 1) // 2 + 1))
    # Report generator: 3n^2 <= f(n) <= 63n^2 and f(n)/n unbounded
    ok.append(all(3 * n * n <= 3 * n * n + 10 * n * log2(n) + 50 <= 63 * n * n
                  for n in range(1, 20000)))
    ok.append(report_generator_ops(10**6) / 10**6 > report_generator_ops(10**3) / 10**3)
    return all(ok)


# ----------------------------------------------------------------------- main
def main():
    n = N_FUTURE
    m1 = m1_comparisons(n)
    m2_small, m2_big = m2_audits(1024), m2_audits(n)
    s2 = s2_comparisons(n)
    s1 = s1_expected(n, Fraction(1, 2))
    m4_cur = recurrence_cost(4, f_linear, n)
    m4_new = recurrence_cost(2, f_linear, n)
    m5 = recurrence_cost(2, f_nlogn, n)
    rep = report_generator_ops(n)

    print("SHOPSPHERE SCALABILITY AUDIT  (n = 1,000,000; 10^8 ops/s; 600 s window)")
    print()
    print(f"M1 comparisons (n=1,000,000): {m1:,}  [exact]")
    print(f"M2 audits (n=1,024): {m2_small:,}  [exact]")
    print(f"M2 audits (n=1,000,000): {m2_big:,}  [exact]")
    print(f"S2 recurrence comparisons: {s2}  [exact, T(1)=1]")
    print(f"S1 expected comparisons (p=0.5): {float(s1):,.2f}  [exact]")
    print()
    print(f"M4 current: Theta(n^2); model work {m4_cur:,}; est. time {seconds(m4_cur):,.1f} s  [model]")
    print(f"M4 redesign: Theta(n log n); model work {m4_new:,}; est. time {seconds(m4_new):.3f} s  [model]")
    print(f"M5: Theta(n log^2 n); model work {m5:,}; est. time {seconds(m5):.3f} s  [model]")
    print()
    print(f"{'Module':<14}{'Work (ops)':>20}{'Time (s)':>14}  Window")
    rows = [("M1", m1), ("M2", m2_big), ("S2 (1 query)", s2),
            ("M4 current", m4_cur), ("M4 redesign", m4_new), ("M5", m5),
            ("Report gen.", rep)]
    for name, ops in rows:
        sec = seconds(ops)
        print(f"{name:<14}{ops:>20,}{sec:>14,.7g}  {verdict(sec)}")
    print()
    print("600-second window: results calculated")
    if not run_checks():
        raise SystemExit("Formula checks: FAILED")
    print("Formula checks: PASSED")
    print("Audit completed successfully.")


if __name__ == "__main__":
    main()
