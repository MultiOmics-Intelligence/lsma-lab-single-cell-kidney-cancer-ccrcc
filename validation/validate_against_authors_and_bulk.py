# Validation of the single-cell run: (1) lab labels vs the authors' labels, (2) where the bulk TCGA tumour genes sit.
import sys, json, numpy as np, pandas as pd, anndata as ad, scipy.sparse as sp
h5, up, dn, out = sys.argv[1:5]
a = ad.read_h5ad(h5)
obs = a.obs
lab = obs["cell_type_predicted"].astype(str) if "cell_type_predicted" in obs else obs["cell_type"].astype(str)
auth = obs["author_cell_type"].astype(str)
ct = pd.crosstab(auth, lab); ct.to_csv(f"{out}/sc_author_vs_lab_crosstab.tsv", sep="\t")
# agreement: map author fine labels to the lab's broad labels
m = {"Tumor": "ccRCC tumour cells", "Tcell_CD8": "CD8 T cells", "Tcell": "T cells", "Macro": "Macrophages", "Macro_MKI67": "Macrophages",
     "Bcell": "B cells", "Plasma": "Plasma cells", "Mast": "Mast cells", "Endo_ACKR1": "Endothelial cells", "Endo_PLVAP": "Endothelial cells",
     "Peri": "Pericytes", "vSMC": "Smooth muscle cells"}
broad = {"CD4 T cells": "T cells", "CD8 T cells": "T cells", "Regulatory T cells": "T cells", "NK cells": "T/NK cells",
         "Monocytes": "Myeloid", "Macrophages": "Myeloid", "Dendritic cells": "Myeloid", "Pericytes": "Pericytes/SMC", "Smooth muscle cells": "Pericytes/SMC"}
def b(x): 
    x = broad.get(x, x); return "T cells" if x in ("T/NK cells",) else x
la = auth.map(lambda x: b(m.get(x, x))); ll = lab.map(b)
la = la.replace({"T cells": "T/NK"}); ll = ll.replace({"T cells": "T/NK", "T/NK cells": "T/NK"})
agree = (la == ll)
per = pd.DataFrame({"author_label": auth, "agree": agree}).groupby("author_label").agg(n_cells=("agree", "size"), agreement=("agree", "mean")).round(3)
per.to_csv(f"{out}/sc_agreement_by_author_label.tsv", sep="\t")
# bulk genes
X = a.layers["counts"] if "counts" in a.layers else (a.raw.X if a.raw is not None else a.X)
names = list(a.var_names) if X.shape[1] == a.n_vars else list(a.raw.var_names)
X = sp.csr_matrix(X); lib = np.asarray(X.sum(1)).ravel(); Xn = sp.diags(1e4 / np.maximum(lib, 1)) @ X; Xn.data = np.log1p(Xn.data)
idx = {g: i for i, g in enumerate(names)}
def score(genes):
    g = [x for x in genes if x in idx]
    return np.asarray(Xn[:, [idx[x] for x in g]].mean(1)).ravel(), len(g)
upg = pd.read_csv(up, sep="\t")["symbol"].dropna().tolist(); dng = pd.read_csv(dn, sep="\t")["symbol"].dropna().tolist()
su, nu = score(upg); sd, nd = score(dng)
df = pd.DataFrame({"cell_type": lab.values, "bulk_up_score": su, "bulk_down_score": sd})
tab = df.groupby("cell_type").agg(n_cells=("bulk_up_score", "size"), mean_score_genes_up_in_tumour=("bulk_up_score", "mean"), mean_score_genes_down_in_tumour=("bulk_down_score", "mean")).round(4).sort_values("mean_score_genes_up_in_tumour", ascending=False)
tab.to_csv(f"{out}/sc_bulk_tumour_genes_by_cell_type.tsv", sep="\t")
genes = ["CA9", "NDUFA4L2", "ANGPTL4", "EGLN3", "VEGFA", "CXCL10", "UMOD", "SLC12A1"]
rows = {}
for g in genes:
    if g in idx:
        v = np.asarray(Xn[:, idx[g]].todense()).ravel()
        rows[g] = pd.Series(v).groupby(lab.values).apply(lambda s: (s > 0).mean()).round(3)
pct = pd.DataFrame(rows); pct.to_csv(f"{out}/sc_marker_genes_fraction_expressing.tsv", sep="\t")
print("cells", a.n_obs, "| overall agreement", round(agree.mean(), 3)); print(per.to_string()); print("bulk up genes found", nu, "down", nd); print(tab.to_string()); print(pct.to_string())
