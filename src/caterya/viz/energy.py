"""Fairness energy map: a plot of a declared parity formula, not a physical landscape.

For two groups the height is ``z = 1 - |x - y|`` where ``x`` and ``y`` are
positive rates. The surface is that formula on a grid. The marker is the
observed pair. The canonical grid is what gets hashed; HTML from Plotly is an
optional rendering of the same grid and is not the hashed artifact.
"""
from __future__ import annotations

from typing import Any, Optional, Sequence

from ..core.canonical import digest
from ..core.errors import CapabilityUnavailable, ConfigError

FORMULA = "z = 1 - |x - y| on a uniform grid in [0, 1]^2; marker = (rate_a, rate_b, z)"
LIMITATIONS = (
    "Visualisation of demographic parity for two groups. Not an independent measurement and not an energy in the physical sense.",
    "Valleys are just |rate_a - rate_b| by definition. The picture cannot reveal bias that was not in the two rates.",
    "The artifact hash covers the canonical grid, not the HTML, which may include library versions and nondeterministic ids.",
    "Research-grade. More than two groups are not projected into this surface; pass an explicit pair.",
)


def _linspace(n: int) -> list[float]:
    if n < 2:
        raise ConfigError("grid must be >= 2")
    return [i / (n - 1) for i in range(n)]


def build_surface(rate_a: float, rate_b: float, *, grid: int = 21, label_a: str = "a", label_b: str = "b") -> dict[str, Any]:
    """Return the canonical artifact (JSON-ready) and its digest."""
    if not 0.0 <= rate_a <= 1.0 or not 0.0 <= rate_b <= 1.0:
        raise ConfigError("rates must be in [0, 1]")
    xs = _linspace(grid)
    z = [[1.0 - abs(x - y) for x in xs] for y in xs]
    marker_z = 1.0 - abs(rate_a - rate_b)
    artifact = {
        "formula": FORMULA,
        "grid": grid,
        "x": xs,
        "y": xs,
        "z": z,
        "marker": {"label_a": label_a, "label_b": label_b, "rate_a": rate_a, "rate_b": rate_b, "z": marker_z},
        "limitations": list(LIMITATIONS),
        "status": "research",
    }
    return {"artifact": artifact, "artifact_hash": digest(artifact), "marker_parity": marker_z}


def render_html(surface: dict[str, Any]) -> str:
    """Plotly HTML for ``surface['artifact']``. Raises if Plotly is not installed."""
    try:
        import plotly.graph_objects as go
    except Exception as exc:
        raise CapabilityUnavailable("plotly is not installed. pip install 'caterya[viz]'. The hashed grid is still available.") from exc
    art = surface["artifact"]
    fig = go.Figure(
        data=[
            go.Surface(x=art["x"], y=art["y"], z=art["z"], colorscale="Greys", showscale=True, name="1-|x-y|"),
            go.Scatter3d(
                x=[art["marker"]["rate_a"]],
                y=[art["marker"]["rate_b"]],
                z=[art["marker"]["z"]],
                mode="markers",
                marker={"size": 6, "color": "black"},
                name="observed",
            ),
        ]
    )
    fig.update_layout(
        title="Fairness parity surface (research visualisation, not a physical energy)",
        scene={"xaxis_title": art["marker"]["label_a"], "yaxis_title": art["marker"]["label_b"], "zaxis_title": "1-|x-y|"},
        margin={"l": 0, "r": 0, "t": 40, "b": 0},
    )
    return fig.to_html(include_plotlyjs="cdn", full_html=True)


def rates_from_pairs(rows: Sequence[dict], group_a: str, group_b: str) -> tuple[float, float]:
    """Mean ``y_pred`` for two named groups."""
    buckets: dict[str, list[float]] = {group_a: [], group_b: []}
    for row in rows:
        label = str(row.get("group"))
        if label not in buckets:
            continue
        pred = row["y_pred"] if "y_pred" in row else row["prediction"]
        buckets[label].append(float(pred))
    if not buckets[group_a] or not buckets[group_b]:
        raise ConfigError(f"need at least one row for each of {group_a!r} and {group_b!r}")
    return sum(buckets[group_a]) / len(buckets[group_a]), sum(buckets[group_b]) / len(buckets[group_b])


def surface_for_rows(rows: Sequence[dict], group_a: str, group_b: str, *, grid: int = 21) -> dict[str, Any]:
    """Build a surface from rows. ``group_a`` and ``group_b`` must be explicit."""
    ra, rb = rates_from_pairs(rows, group_a, group_b)
    return build_surface(ra, rb, grid=grid, label_a=group_a, label_b=group_b)


def maybe_html(surface: dict[str, Any]) -> Optional[str]:
    """HTML when Plotly imports; ``None`` when it does not. Never invents a figure."""
    try:
        return render_html(surface)
    except CapabilityUnavailable:
        return None
