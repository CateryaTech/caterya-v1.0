from __future__ import annotations

import html

_ARROW = {"pass": "PASS", "warn": "WARN", "fail": "FAIL", "inconclusive": "INCONCLUSIVE", "untested": "NOT TESTED", "info": "INFO"}


def render_markdown(car: dict, evidences: list | None = None) -> str:
    L = [f"# CATERYA Assurance Record — {car['car_id']} (v{car['version']})", "",
         f"**System:** {car['system']['name']} {car['system']['version']} · **Profile:** {car['evaluation']['profile']} · "
         f"**Mode:** {car['evaluation']['mode']}",
         f"**Assurance level:** {car['level']} — {car['level_label']} · **Disposition:** {car['disposition']['status']} "
         f"(recommended: {car['disposition']['recommended']}) · **Risk:** {car['risk']['level']} (residual {car['risk']['residual_level']})",
         f"**Valid:** {car['validity']['issued_at']} → {car['validity']['valid_until']}", "",
         "| Domain | Metric | Value | 95% CI | n | Status |", "|---|---|---|---|---|---|"]
    for dn, d in sorted(car["domains"].items()):
        for mid, m in d["metrics"].items():
            v = "—" if m["value"] is None else f"{m['value']:.3f}"
            ci = "—" if not m["ci_95"] else f"[{m['ci_95'][0]:.2f}, {m['ci_95'][1]:.2f}]"
            L.append(f"| {dn} | `{mid}` | {v} | {ci} | {m['n']} | {_ARROW.get(m['status'], m['status'])} |")
    L += ["", "## Findings"] + ([f"- **{f['severity'].upper()}** {f['message']}" for f in car["risk"]["findings"]] or ["- none"])
    L += ["", "## Not tested / gaps"] + ([f"- {u}" for u in car["coverage"]["untested"]] or ["- none declared"])
    L += ["", "## Conditions"] + ([f"- {c}" for c in car["disposition"]["conditions"]] or ["- none"])
    cos = car["cos"]
    L += ["", f"## Derived index\nCOS = {('%.3f' % cos['cos']) if cos.get('cos') is not None else 'n/a'} "
              f"(coverage {cos.get('coverage', 0):.0%}). {cos.get('note', '')}"]
    L += ["", "## Provenance", f"- Evidence records: {car['evidence']['count']}", f"- Merkle root: `{car['evidence']['merkle_root']}`",
          f"- CAR hash: `{car['content_hash']}`", f"- Signed by: `{car['signer']['key_id']}` ({car['signer']['alg']})", "",
          f"> {car['disclaimer']}"]
    if car["disposition"]["decided_by"]:
        L += ["", f"**Governance decision:** {car['disposition']['status']} by {car['disposition']['decided_by']} "
                  f"({car['disposition']['role']}) — {car['disposition']['rationale']}"]
    return "\n".join(L)


def render_html(car: dict) -> str:
    rows = "".join(
        f"<tr><td>{html.escape(dn)}</td><td class=m>{html.escape(mid)}</td><td>{'—' if m['value'] is None else '%.3f' % m['value']}</td>"
        f"<td>{html.escape(_ARROW.get(m['status'], m['status']))}</td></tr>"
        for dn, d in sorted(car["domains"].items()) for mid, m in d["metrics"].items())
    return f"""<!doctype html><html><head><meta charset=utf-8><title>{html.escape(car['car_id'])}</title>
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@500;700&family=Exo+2:wght@400;600&display=swap" rel=stylesheet>
<style>body{{background:#fff;color:#12161c;font-family:'Exo 2',system-ui,sans-serif;max-width:860px;margin:40px auto;padding:0 20px}}
h1{{font-family:Orbitron,sans-serif;font-size:22px;letter-spacing:.04em}}table{{border-collapse:collapse;width:100%}}
td,th{{border-bottom:1px solid #d7dde6;padding:6px 8px;text-align:left}}.m{{font-family:ui-monospace,monospace;font-size:13px}}</style></head>
<body><h1>{html.escape(car['car_id'])} · {html.escape(car['system']['name'])}</h1>
<p>Level {car['level']} ({html.escape(car['level_label'])}) · {html.escape(car['disposition']['status'])} · risk {html.escape(car['risk']['level'])}</p>
<table><tr><th>Domain</th><th>Metric</th><th>Value</th><th>Status</th></tr>{rows}</table>
<p class=m>root {html.escape(car['evidence']['merkle_root'])}<br>hash {html.escape(car['content_hash'])}</p>
<p>{html.escape(car['disclaimer'])}</p></body></html>"""
