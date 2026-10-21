"""Padrões e agrupamentos de municípios + fatores associados à demanda.

1. KMeans sobre indicadores padronizados de cada município (k escolhido pela
   silhueta entre 3 e 4, para que os grupos sejam legíveis). PCA 2D para visualizar.
2. Fatores associados à taxa de internação (por 1.000 hab.):
   - correlação de Spearman de cada fator com a taxa;
   - regressão linear (OLS, erros robustos HC3) com variáveis padronizadas,
     ponderada pela população. Mostra associação, não causalidade.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.stats import spearmanr
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

from analysis.common import query, save

FEATURES = {
    "taxa_int_1k": "Internações por 1.000 hab.",
    "perm_media": "Permanência média (dias)",
    "valor_medio": "Valor médio por internação (R$)",
    "pct_urgencia": "% urgência",
    "pct_idosos": "% de internações de idosos (60+)",
    "pct_fora": "% internados fora do município",
    "leitos_sus_10k": "Leitos SUS por 10 mil hab.",
    "ubs_10k": "UBS por 10 mil hab.",
    "log_pop": "População (log)",
    "amplitude_sazonal": "Amplitude sazonal",
}

FATORES = {
    "pct_idosos": "% de internações de idosos (60+)",
    "leitos_sus_10k": "Leitos SUS por 10 mil hab.",
    "ubs_10k": "UBS por 10 mil hab.",
    "log_pop": "Porte do município (log da população)",
    "log_densidade": "Densidade demográfica (log)",
    "pct_fora": "% internados fora do município",
    "pct_urgencia": "% urgência",
    "pct_resp": "% causas respiratórias",
    "amplitude_sazonal": "Amplitude sazonal",
}


def amplitude_sazonal(con) -> pd.DataFrame:
    d = query(con, """SELECT mun_res AS cod_mun, mes_inter, SUM(internacoes) n
                      FROM agg_mensal_res GROUP BY 1, 2""")
    d["mes"] = d["mes_inter"].str[5:].astype(int)
    m = d.groupby(["cod_mun", "mes"])["n"].mean().unstack(fill_value=0)
    idx = m.div(m.mean(axis=1), axis=0)
    # amplitude = (pico - vale) / média, suavizada com média móvel de 3 meses
    smooth = idx.T.rolling(3, center=True, min_periods=1).mean().T
    return (smooth.max(axis=1) - smooth.min(axis=1)).rename("amplitude_sazonal").reset_index()


def nomear(perfil: pd.DataFrame) -> dict[int, str]:
    """Rótulo legível de cada grupo pelos dois traços mais marcantes (z-score)."""
    z = (perfil - perfil.mean()) / perfil.std(ddof=0)
    curtos = {"taxa_int_1k": "taxa de internação", "perm_media": "permanência",
              "valor_medio": "custo médio", "pct_urgencia": "% urgência",
              "pct_idosos": "% idosos", "pct_fora": "internação fora",
              "leitos_sus_10k": "leitos/hab.", "ubs_10k": "UBS/hab.",
              "log_pop": "porte", "amplitude_sazonal": "sazonalidade"}
    nomes = {}
    for c, row in z.iterrows():
        top = row.abs().sort_values(ascending=False).index[:3]
        nomes[c] = " · ".join(("↑ " if row[f] > 0 else "↓ ") + curtos[f] for f in top)
    return nomes


def run(con, mun: pd.DataFrame) -> None:
    df = mun.merge(amplitude_sazonal(con), on="cod_mun", how="left")
    df["log_pop"] = np.log10(df["pop"])
    df["log_densidade"] = np.log10(df["densidade"])
    df = df[df["int_res"] > 0].copy()
    cols = list(FEATURES)
    X = df[cols].fillna(df[cols].median())
    # winsorize 1%-99% para reduzir o efeito de municípios muito pequenos
    X = X.clip(X.quantile(0.01), X.quantile(0.99), axis=1)
    Xs = StandardScaler().fit_transform(X)

    best = None
    for k in (3, 4):
        km = KMeans(n_clusters=k, n_init=20, random_state=42).fit(Xs)
        s = silhouette_score(Xs, km.labels_)
        print(f"  k={k}: silhueta={s:.3f}")
        if best is None or s > best[0]:
            best = (s, k, km)
    _, k, km = best

    # ordena grupos pela taxa média de internação (grupo 1 = maior demanda)
    df["cluster_raw"] = km.labels_
    ordem = (df.groupby("cluster_raw")["taxa_int_1k"].mean()
               .sort_values(ascending=False).index.tolist())
    df["cluster"] = df["cluster_raw"].map({c: i + 1 for i, c in enumerate(ordem)})
    pcs = PCA(n_components=2, random_state=42).fit(Xs)
    df[["pc1", "pc2"]] = pcs.transform(Xs)

    perfil = df.groupby("cluster")[cols].mean()
    nomes = nomear(perfil)
    perfil = perfil.reset_index()
    perfil["nome"] = perfil["cluster"].map(nomes)
    perfil["n_municipios"] = perfil["cluster"].map(df["cluster"].value_counts())
    perfil["populacao"] = perfil["cluster"].map(df.groupby("cluster")["pop"].sum())
    df["cluster_nome"] = df["cluster"].map(nomes)
    save(con, "res_cluster_municipio",
         df[["cod_mun", "nome", "drs_nome", "pop", "cluster", "cluster_nome", "pc1", "pc2",
             "lat", "lon"] + [c for c in cols if c not in ("pop",)]])
    save(con, "res_cluster_perfil", perfil)
    var = pcs.explained_variance_ratio_
    save(con, "res_cluster_meta", pd.DataFrame({
        "k": [k], "silhueta": [best[0]], "pc1_var": [var[0]], "pc2_var": [var[1]],
        "features": [", ".join(FEATURES[c] for c in cols)]}))

    # ---- fatores associados à demanda --------------------------------------
    alvo = "taxa_int_1k"
    d = df[[alvo] + list(FATORES) + ["pop"]].replace([np.inf, -np.inf], np.nan).dropna()
    d = d[d["pop"] >= 5000]  # taxas muito instáveis em municípios minúsculos
    rows = []
    for f, label in FATORES.items():
        rho, p = spearmanr(d[f], d[alvo])
        rows.append({"fator": f, "rotulo": label, "spearman": rho, "p_spearman": p})
    fat = pd.DataFrame(rows)

    Z = (d[list(FATORES)] - d[list(FATORES)].mean()) / d[list(FATORES)].std()
    y = (d[alvo] - d[alvo].mean()) / d[alvo].std()
    ols = sm.WLS(y, sm.add_constant(Z), weights=np.sqrt(d["pop"])).fit(cov_type="HC3")
    ci = ols.conf_int()
    fat["coef"] = fat["fator"].map(ols.params)
    fat["ci_low"] = fat["fator"].map(ci[0])
    fat["ci_high"] = fat["fator"].map(ci[1])
    fat["p_coef"] = fat["fator"].map(ols.pvalues)
    fat["r2"] = ols.rsquared
    fat["n"] = len(d)
    print(f"  regressão: R²={ols.rsquared:.2f}, n={len(d)}")
    save(con, "res_fatores", fat.sort_values("coef", key=abs, ascending=False))
