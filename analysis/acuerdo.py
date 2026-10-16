"""Exactitud factual y acuerdo entre anotadores a partir de data/anotacion/.
Uso: python3 analysis/acuerdo.py
Exactitud: etiquetas de A tras consenso (30 artículos). Acuerdo: etiquetas ciegas de A
frente a las de B (10 artículos). IC 95 % por bootstrap de artículos (10 000 réplicas)."""
import csv, json, os, random
from collections import Counter
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "anotacion")
cargar = lambda n: json.load(open(os.path.join(D, n), encoding="utf-8"))
ETQ = ["R", "D", "C", "EC", "EI", "EN"]
GRUPO = {"R": "OK", "EC": "OK", "D": "ERR", "C": "ERR", "EI": "ERR", "EN": "NV"}

def ic(valores):
    v = sorted(valores); return v[len(v) // 40 - 1], v[len(v) * 39 // 40 - 1]

def tasas(A, arts):
    c = Counter(f["etiqueta"] for a in arts for f in A[a]); n = sum(c.values())
    return {"fidelidad (R)": c["R"] / n, "error (D+C+EI)": (c["D"] + c["C"] + c["EI"]) / n,
            "externa (EC+EI+EN)": (c["EC"] + c["EI"] + c["EN"]) / n, "R+EC": (c["R"] + c["EC"]) / n}

A = cargar("etiquetas_A_consenso.json"); arts = sorted(A)
c = Counter(f["etiqueta"] for a in arts for f in A[a]); n = sum(c.values())
print("== Exactitud: %d artículos, %d afirmaciones" % (len(arts), n))
for e in ETQ:
    print("  %-2s %3d  %5.1f %%" % (e, c[e], 100 * c[e] / n))
rng = random.Random(20261014); boot = [tasas(A, [rng.choice(arts) for _ in arts]) for _ in range(10000)]
for k, v in tasas(A, arts).items():
    lo, hi = ic([b[k] for b in boot]); print("  %-20s %5.1f %%  IC95 [%.1f, %.1f]" % (k, 100 * v, 100 * lo, 100 * hi))
print("  artículos sin error: %d/%d" % (sum(not any(f["etiqueta"] in ("D", "C", "EI") for f in A[a]) for a in arts), len(arts)))

def kappa(p):
    n = len(p); po = sum(a == b for a, b in p) / n
    ca, cb = Counter(a for a, _ in p), Counter(b for _, b in p)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / n ** 2
    return (po - pe) / (1 - pe) if pe < 1 else 1.0

def ac1(p, cats):
    n = len(p); po = sum(a == b for a, b in p) / n; c = Counter(x for t in p for x in t)
    pe = sum(c[k] / (2 * n) * (1 - c[k] / (2 * n)) for k in cats) / (len(cats) - 1)
    return (po - pe) / (1 - pe)

Aci = cargar("etiquetas_A_ciegas.json")
B = list(csv.DictReader(open(os.path.join(D, "etiquetas_B.csv"), encoding="utf-8")))
na = sum(r["etiqueta"] == "NA" for r in B)
filas = [(r["articulo"], Aci[r["articulo"]][int(r["n"]) - 1]["etiqueta"], r["etiqueta"]) for r in B if r["etiqueta"] not in ("", "NA")]
print("\n== Acuerdo: %d afirmaciones listadas, %d marcadas NA por B, %d comparadas" % (len(B), na, len(filas)))
sub = sorted(set(a for a, _, _ in filas)); rng = random.Random(20261016)
muestras = [[f for a in [rng.choice(sub) for _ in sub] for f in filas if f[0] == a] for _ in range(10000)]
for nombre, cats, g in (("6 etiquetas", ETQ, lambda e: e), ("3 grupos", ["OK", "ERR", "NV"], GRUPO.get)):
    par = lambda fs: [(g(a), g(b)) for _, a, b in fs]
    p = par(filas); po = sum(a == b for a, b in p) / len(p); q = len(cats)
    k_ic = ic([kappa(par(m)) for m in muestras]); a_ic = ic([ac1(par(m), cats) for m in muestras])
    print("  %-11s acuerdo %.1f %% | kappa %.3f [%.3f, %.3f] | AC1 %.3f [%.3f, %.3f] | PABAK %.3f"
          % (nombre, 100 * po, kappa(p), k_ic[0], k_ic[1], ac1(p, cats), a_ic[0], a_ic[1], (q * po - 1) / (q - 1)))
