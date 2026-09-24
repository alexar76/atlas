"""Stdlib math behind ATLAS field products.

These are the same estimators the oracle family sells as priced hops
(Murmuration, Lattice, Gauss, Betti H0). ATLAS runs them locally on a LIVE
in-situ mesh so the paid artifact is one receipt, not a federated round-trip.
The sibling oracle ids stay on the payload so a buyer can replay the hop.

No numpy. Atlas does not take a numpy dependency for a dozen stations.
"""

from __future__ import annotations

import math
from typing import Any, Sequence

BIWEIGHT_C = 4.685
_EPS = 1e-12
_ONE_MINUS_EPS = math.nextafter(1.0, 0.0)
HALTON_PRIMES: tuple[int, ...] = (2, 3, 5, 7, 11, 13, 17, 19)
MAX_HALTON_COUNT = 4096
MAX_GP_OBS = 64


def _finite(values: Sequence[Any]) -> list[float]:
    out: list[float] = []
    for item in values:
        try:
            number = float(item)
        except (TypeError, ValueError) as exc:
            raise ValueError("values must all be finite numbers") from exc
        if not math.isfinite(number):
            raise ValueError("values must all be finite numbers")
        out.append(number)
    if not out:
        raise ValueError("values must contain at least one element")
    return out


def median(values: Sequence[Any]) -> float:
    arr = sorted(_finite(values))
    n = len(arr)
    mid = n // 2
    if n % 2:
        return arr[mid]
    return 0.5 * (arr[mid - 1] + arr[mid])


def trimmed_mean(values: Sequence[Any], trim: float = 0.1) -> float:
    arr = sorted(_finite(values))
    n = len(arr)
    t = min(max(float(trim), 0.0), 0.499)
    k = int(math.floor(n * t))
    if 2 * k >= n:
        return median(arr)
    kept = arr[k : n - k]
    return sum(kept) / len(kept)


def mad(values: Sequence[Any], center: float | None = None) -> float:
    arr = _finite(values)
    c = median(arr) if center is None else float(center)
    return 1.4826 * median([abs(x - c) for x in arr])


def biweight_location(
    values: Sequence[Any], c: float = BIWEIGHT_C, max_iter: int = 50, tol: float = 1e-9
) -> float:
    arr = _finite(values)
    if len(arr) == 1:
        return arr[0]
    t = median(arr)
    scale = mad(arr, center=t)
    if scale < _EPS:
        return t
    denom = c * scale
    for _ in range(max_iter):
        weights: list[float] = []
        any_in = False
        for x in arr:
            u = (x - t) / denom
            if abs(u) < 1.0:
                any_in = True
                weights.append((1.0 - u * u) ** 2)
            else:
                weights.append(0.0)
        if not any_in:
            return median(arr)
        wsum = sum(weights)
        if wsum < _EPS:
            return median(arr)
        t_new = sum(w * x for w, x in zip(weights, arr)) / wsum
        if abs(t_new - t) <= tol * (abs(t) + tol):
            t = t_new
            break
        t = t_new
    return t


def degroot_consensus(
    values: Sequence[Any], max_iter: int = 1000, tol: float = 1e-9
) -> dict[str, Any]:
    x = _finite(values)
    n = len(x)
    if n == 1:
        return {"converged_value": x[0], "iterations": 0}
    iterations = 0
    for _ in range(max_iter):
        spread = max(x) - min(x)
        if spread <= tol:
            break
        mean = sum(x) / n
        x = [mean] * n
        iterations += 1
    return {"converged_value": sum(x) / n, "iterations": iterations}


def aggregate(values: Sequence[Any], trim: float = 0.1) -> dict[str, Any]:
    arr = _finite(values)
    dg = degroot_consensus(arr)
    return {
        "n": len(arr),
        "median": median(arr),
        "trimmed_mean": trimmed_mean(arr, trim),
        "biweight": biweight_location(arr),
        "converged_value": dg["converged_value"],
        "iterations": dg["iterations"],
        "algorithm": "murmuration-equivalent",
        "sibling_oracle": "murmuration.aggregate@v1",
    }


def radical_inverse(n: int, base: int) -> float:
    if base < 2:
        raise ValueError("base must be >= 2")
    result = 0.0
    f = 1.0 / base
    i = n
    while i > 0:
        result += (i % base) * f
        i //= base
        f /= base
    if result >= 1.0:
        return _ONE_MINUS_EPS
    return result


def halton(count: int, dim: int = 2, skip: int = 0) -> list[list[float]]:
    count = int(count)
    dim = int(dim)
    skip = int(skip)
    if not (1 <= count <= MAX_HALTON_COUNT):
        raise ValueError(f"count must be in 1..{MAX_HALTON_COUNT}")
    if not (1 <= dim <= len(HALTON_PRIMES)):
        raise ValueError(f"dim must be in 1..{len(HALTON_PRIMES)}")
    if skip < 0:
        raise ValueError("skip must be >= 0")
    bases = HALTON_PRIMES[:dim]
    start = 1 + skip
    return [[radical_inverse(n, b) for b in bases] for n in range(start, start + count)]


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def _cholesky(matrix: list[list[float]]) -> list[list[float]]:
    n = len(matrix)
    lower = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1):
            acc = sum(lower[i][k] * lower[j][k] for k in range(j))
            if i == j:
                diag = matrix[i][i] - acc
                if diag <= 0:
                    raise ValueError("covariance is not positive definite")
                lower[i][j] = math.sqrt(diag)
            else:
                lower[i][j] = (matrix[i][j] - acc) / lower[j][j]
    return lower


def _forward_sub(lower: list[list[float]], b: list[float]) -> list[float]:
    n = len(b)
    y = [0.0] * n
    for i in range(n):
        acc = b[i] - sum(lower[i][j] * y[j] for j in range(i))
        y[i] = acc / lower[i][i]
    return y


def _back_sub(lower: list[list[float]], y: list[float]) -> list[float]:
    n = len(y)
    x = [0.0] * n
    for i in range(n - 1, -1, -1):
        acc = y[i] - sum(lower[j][i] * x[j] for j in range(i + 1, n))
        x[i] = acc / lower[i][i]
    return x


def rbf_gp_posterior(
    train: Sequence[tuple[float, float, float]],
    queries: Sequence[tuple[float, float]],
    *,
    length_km: float = 120.0,
    signal_var: float = 1.0,
    noise_var: float = 1e-4,
) -> list[dict[str, float]]:
    """Spatial RBF GP over (lat, lon) → scalar. Snapshot interpolation, not a forecast.

    Sibling: ``gauss.field@v1``. Length-scale is kilometres (haversine).
    """
    if not train:
        raise ValueError("train must contain at least one observation")
    if len(train) > MAX_GP_OBS:
        raise ValueError(f"at most {MAX_GP_OBS} observations")
    cleaned: list[tuple[float, float, float]] = []
    for lat, lon, val in train:
        try:
            plat, plon, pval = float(lat), float(lon), float(val)
        except (TypeError, ValueError) as exc:
            raise ValueError("train observations must be finite numbers") from exc
        if not (math.isfinite(plat) and math.isfinite(plon) and math.isfinite(pval)):
            raise ValueError("train observations must be finite numbers")
        cleaned.append((plat, plon, pval))
    train = cleaned
    query_pts: list[tuple[float, float]] = []
    for qlat, qlon in queries:
        try:
            plat, plon = float(qlat), float(qlon)
        except (TypeError, ValueError) as exc:
            raise ValueError("query coordinates must be finite numbers") from exc
        if not (math.isfinite(plat) and math.isfinite(plon)):
            raise ValueError("query coordinates must be finite numbers")
        query_pts.append((plat, plon))
    try:
        length = float(length_km)
        sf = float(signal_var)
        sn = float(noise_var)
    except (TypeError, ValueError) as exc:
        raise ValueError("GP hyperparameters must be finite numbers") from exc
    if not (math.isfinite(length) and math.isfinite(sf) and math.isfinite(sn)):
        raise ValueError("GP hyperparameters must be finite numbers")
    n = len(train)
    length = max(length, 1.0)
    sf = max(sf, 1e-9)
    sn = max(sn, 1e-9)

    def k(a: tuple[float, float], b: tuple[float, float]) -> float:
        d = haversine_km(a[0], a[1], b[0], b[1])
        return sf * math.exp(-0.5 * (d / length) ** 2)

    cov = [[0.0] * n for _ in range(n)]
    y = [0.0] * n
    for i, (lat_i, lon_i, val_i) in enumerate(train):
        y[i] = val_i
        for j in range(i, n):
            lat_j, lon_j, _ = train[j]
            value = k((lat_i, lon_i), (lat_j, lon_j))
            if i == j:
                value += sn
            cov[i][j] = value
            cov[j][i] = value
    lower = _cholesky(cov)
    alpha = _back_sub(lower, _forward_sub(lower, y))
    out: list[dict[str, float]] = []
    for qlat, qlon in query_pts:
        kvec = [k((qlat, qlon), (lat, lon)) for lat, lon, _ in train]
        mean = sum(a * kv for a, kv in zip(alpha, kvec))
        v = _forward_sub(lower, kvec)
        var = max(k((qlat, qlon), (qlat, qlon)) - sum(vi * vi for vi in v), 0.0)
        out.append({"lat": qlat, "lon": qlon, "mean": mean, "variance": var, "std": math.sqrt(var)})
    return out


def h0_persistence(
    points: Sequence[tuple[float, float]],
    *,
    max_km: float = 400.0,
    steps: int = 16,
) -> dict[str, Any]:
    """Connected-component (H0) barcode of a geographic point set.

    This is the 0-dimensional half of a Vietoris–Rips filtration. It is not
    Betti-1 loops and not ``betti.homology@v1``. Sibling oracle for full VR.
    """
    coords: list[tuple[float, float]] = []
    for lat, lon in points:
        try:
            plat, plon = float(lat), float(lon)
        except (TypeError, ValueError) as exc:
            raise ValueError("points must be finite coordinates") from exc
        if not (math.isfinite(plat) and math.isfinite(plon)):
            raise ValueError("points must be finite coordinates")
        coords.append((plat, plon))
    n = len(coords)
    if n == 0:
        raise ValueError("need at least one point")
    try:
        radius_cap = float(max_km)
        n_steps = int(steps)
    except (TypeError, ValueError) as exc:
        raise ValueError("max_km and steps must be finite") from exc
    if not math.isfinite(radius_cap) or radius_cap < 0 or n_steps < 1:
        raise ValueError("max_km and steps must be finite")
    radii = [radius_cap * (i / n_steps) for i in range(n_steps + 1)]
    series: list[dict[str, Any]] = []
    for radius in radii:
        parent = list(range(n))

        def find(i: int) -> int:
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        def union(a: int, b: int) -> None:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[rb] = ra

        for i in range(n):
            for j in range(i + 1, n):
                if haversine_km(coords[i][0], coords[i][1], coords[j][0], coords[j][1]) <= radius:
                    union(i, j)
        components = len({find(i) for i in range(n)})
        series.append({"radius_km": round(radius, 3), "components": components})
    return {
        "n": n,
        "filtration": "vietoris-rips-h0",
        "algorithm": "union-find H0",
        "sibling_oracle": "betti.homology@v1",
        "series": series,
        "components_at_max": series[-1]["components"] if series else n,
    }
