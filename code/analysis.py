"""
Bangladesh restaurants dataset - full inspection & analysis.
Run:  python analysis.py restaurants.csv
Outputs: graphs/, facts/, data/restaurants_clean.csv, stats.json
"""
import sys, os, re, json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import reverse_geocoder as rg

SRC = sys.argv[1] if len(sys.argv) > 1 else "restaurants.csv"
OUT = os.path.dirname(os.path.abspath(__file__))
G, F, D = (os.path.join(OUT, x) for x in ("graphs", "facts", "data"))
for p in (G, F, D):
    os.makedirs(p, exist_ok=True)

# ---------- style ----------
GREEN, RED, DARK, GRAY, LIGHT, GOLD = "#006A4E", "#F42A41", "#1F2D2A", "#8A9A95", "#E6EFEC", "#E9B44C"
plt.rcParams.update({
    "figure.dpi": 150, "savefig.dpi": 150, "savefig.bbox": "tight",
    "font.family": "DejaVu Sans", "axes.spines.top": False, "axes.spines.right": False,
    "axes.edgecolor": GRAY, "axes.labelcolor": DARK, "xtick.color": DARK, "ytick.color": DARK,
    "axes.titleweight": "bold", "axes.titlesize": 13, "axes.titlelocation": "left",
    "axes.grid": True, "grid.color": "#DDE6E3", "grid.linewidth": 0.8, "axes.axisbelow": True,
})
S = {}  # all stats collected for facts / script / deck


def save(name, fig=None):
    (fig or plt).savefig(os.path.join(G, name))
    plt.close("all")


def pct(x, d=1):
    return f"{100 * x:.{d}f}%"


# =====================================================================
# 1. LOAD + INSPECT RAW
# =====================================================================
raw = pd.read_csv(SRC)
S["raw_rows"] = len(raw)
S["raw_cols"] = list(raw.columns)
S["exact_dup_rows"] = int(raw.duplicated().sum())
S["raw_unique_place_ids"] = int(raw.place_id.nunique())
S["raw_missing"] = {c: int(raw[c].isna().sum()) for c in raw.columns}

d1 = raw.drop_duplicates().copy()
S["rows_after_exact_dedup"] = len(d1)
conf = d1[d1.place_id.duplicated(keep=False)]
S["conflicting_dup_ids"] = int(conf.place_id.nunique())
# keep the most complete row (has reviews, most reviews) for conflicting ids
d1["_rev"] = d1.number_of_reviews.fillna(-1)
df = d1.sort_values("_rev", ascending=False).drop_duplicates("place_id").drop(columns="_rev").copy()
df = df.sort_index().reset_index(drop=True)
S["unique_places"] = len(df)

# copies per place (how often listings repeat)
copies = raw.groupby("place_id").size()
S["places_repeated"] = int((copies > 1).sum())
S["max_copies"] = int(copies.max())

# =====================================================================
# 2. FEATURE ENGINEERING
# =====================================================================
df["is_unrated"] = (df.rating == 0)
df["has_reviews"] = df.number_of_reviews.notna()
df["has_affluence"] = df.affluence.notna()
df["rated"] = df.rating > 0
df["country"] = np.where(df.address.str.contains(r"India\s*$", regex=True), "India", "Bangladesh")
df["bengali_name"] = df.name.str.contains(r"[\u0980-\u09FF]")
df["bengali_addr"] = df.address.str.contains(r"[\u0980-\u09FF]")
df["plus_code_addr"] = df.address.str.match(r"^[A-Z0-9]{4}\+[A-Z0-9]{2,3}")
df["unnamed_road"] = df.address.str.contains("Unnamed Road", regex=False)

# division via offline reverse geocoder (nearest populated place)
geo = pd.DataFrame(rg.search(list(zip(df.latitude, df.longitude)), mode=1, verbose=False))
div_map = {"Chittagong": "Chattogram", "Barisal": "Barishal", "Rangpur Division": "Rangpur"}
df["division"] = geo.admin1.replace(div_map).replace("", np.nan).values
df.loc[geo.cc.values != "BD", "division"] = np.nan
HQ = {"Dhaka": (23.81, 90.41), "Chattogram": (22.36, 91.78), "Khulna": (22.82, 89.56), "Rajshahi": (24.37, 88.60),
      "Barishal": (22.70, 90.37), "Sylhet": (24.90, 91.87), "Rangpur": (25.74, 89.25)}
need = df.division.isna() & (df.country == "Bangladesh")
for i in df.index[need]:
    df.at[i, "division"] = min(HQ, key=lambda k: (HQ[k][0] - df.at[i, "latitude"]) ** 2 + (HQ[k][1] - df.at[i, "longitude"]) ** 2)
df.loc[df.country == "India", "division"] = "Outside Bangladesh"


def hav(lat1, lon1, lat2, lon2):
    p = np.pi / 180
    a = np.sin((lat2 - lat1) * p / 2) ** 2 + np.cos(lat1 * p) * np.cos(lat2 * p) * np.sin((lon2 - lon1) * p / 2) ** 2
    return 12742 * np.arcsin(np.sqrt(a))


df["km_from_dhaka"] = hav(df.latitude, df.longitude, 23.78, 90.40)
df["greater_dhaka"] = df.km_from_dhaka <= 20

bins = [0, 1, 4, 9, 49, 199, 999, 1e9]
labels = ["1", "2-4", "5-9", "10-49", "50-199", "200-999", "1000+"]
df["review_bucket"] = pd.cut(df.number_of_reviews, bins=bins, labels=labels)

# Bayesian (shrunk) rating: pulls low-review ratings toward the global mean
rated = df[df.rated & df.has_reviews]
M = rated.rating.mean()
C = 25
df["bayes_rating"] = np.where(df.rated & df.has_reviews,
                              (df.number_of_reviews * df.rating + C * M) / (df.number_of_reviews + C), np.nan)

# keyword categories (English + Bengali)
KW = {
    "Hotel (local eatery)": r"hotel|হোটেল",
    "Restaurant": r"restaurant|restora|restur|রেস্টুরেন্ট|রেস্তোরাঁ|রেস্তোরা|রেস্টুরেন্ট",
    "Biryani": r"biry|biriy|biriani|বিরিয়ানি|বিরিয়ানী|বিরানী|কাচ্চি|kacchi|kachchi",
    "Kabab / BBQ": r"kabab|kebab|kebap|কাবাব|কাবার|bbq|grill|tikka|শর্মা|shawarma",
    "Cafe / Coffee": r"cafe|café|coffee|ক্যাফে|কফি",
    "Sweets / Bakery": r"sweet|mishti|misti|মিষ্টি|মিষ্টান্ন|bakery|bekari|বেকারি|বেকারী",
    "Fast food": r"fast ?food|ফাস্ট ?ফুড|pizza|burger|পিজ্জা|পিৎজা|বার্গার|fried chicken|\bkfc\b",
    "Tea stall": r"\btea\b|\bcha\b|টি স্টল|চা স্টল|চায়ের|চা ঘর|টি-স্টল",
    "Canteen": r"canteen|cantin|ক্যান্টিন",
    "Chinese / Thai": r"chinese|thai|চাইনিজ|থাই",
}
for k, pat in KW.items():
    df["kw_" + k] = df.name.str.contains(pat, case=False, regex=True)
STRONG_FOOD = "|".join(KW.values()) + r"|food|ফুড|dine|kitchen|কিচেন|bhoj|ভোজ|juice|জুস|ice ?cream|আইসক্রিম|nasta|নাস্তা|cabin|কেবিন|snack|dhaba|ধাবা|pitha|পিঠা"
NONFOOD = (r"madras|মাদ্রাসা|mosque|মসজিদ|school|স্কুল|furniture|ফার্নিচার|pharmacy|ফার্মেসি|clinic|hospital|\bbank\b|ব্যাংক|"
           r"traders|ট্রেডার্স|enterprise|এন্টারপ্রাইজ|electronic|ইলেকট্রনিক|\bstore\b|ষ্টোর|স্টোর|\bmobile\b|মোবাইল|garments|"
           r"salon|saloon|সেলুন|college|কলেজ|university|poultry|পোল্ট্রি|telecom|টেলিকম|hardware|nursery|ভ্যারাইটিজ|variety|"
           r"\bfarm\b|ফার্ম|steel|স্টীল|পার্টেক্স|eidgah|ঈদগাহ|dormitor|dormetor")
df["likely_non_restaurant"] = df.name.str.contains(NONFOOD, case=False, regex=True) & ~df.name.str.contains(STRONG_FOOD, case=False, regex=True)
df["any_food_keyword"] = df.name.str.contains(STRONG_FOOD, case=False, regex=True)

# =====================================================================
# 3. STATS
# =====================================================================
bd = df[df.country == "Bangladesh"]
S["country_counts"] = df.country.value_counts().to_dict()
S["lat_range"] = [float(df.latitude.min()), float(df.latitude.max())]
S["lon_range"] = [float(df.longitude.min()), float(df.longitude.max())]

# ---- missing / structure
S["n_unrated"] = int(df.is_unrated.sum())
S["share_unrated"] = float(df.is_unrated.mean())
S["n_rated"] = int(df.rated.sum())
S["n_no_reviews"] = int((~df.has_reviews).sum())
S["share_no_reviews"] = float((~df.has_reviews).mean())
S["n_has_aff"] = int(df.has_affluence.sum())
S["share_has_aff"] = float(df.has_affluence.mean())
S["unrated_all_no_reviews"] = bool((df[df.is_unrated].number_of_reviews.isna()).all())
S["rated_but_no_reviews"] = int((df.rated & ~df.has_reviews).sum())
S["aff_min_reviews"] = float(df[df.has_affluence].number_of_reviews.min())
S["aff_unrated_count"] = int((df.has_affluence & df.is_unrated).sum())
S["bengali_name_share"] = float(df.bengali_name.mean())
S["bengali_name_n"] = int(df.bengali_name.sum())
S["plus_code_n"] = int(df.plus_code_addr.sum())
S["plus_code_share"] = float(df.plus_code_addr.mean())
S["unnamed_road_n"] = int(df.unnamed_road.sum())
S["non_rest_n"] = int(df.likely_non_restaurant.sum())
S["non_rest_share"] = float(df.likely_non_restaurant.mean())
S["short_names"] = int((df.name.str.len() <= 3).sum())

# ---- rating
r = df[df.rated]
S["rating_mean"] = float(r.rating.mean())
S["rating_median"] = float(r.rating.median())
S["rating_mode"] = float(r.rating.mode().iloc[0])
S["n_five"] = int((r.rating == 5).sum())
S["share_five_of_rated"] = float((r.rating == 5).mean())
S["n_four_plus"] = int((r.rating >= 4).sum())
S["share_four_plus"] = float((r.rating >= 4).mean())
S["n_below3"] = int((r.rating < 3).sum())
S["share_below3"] = float((r.rating < 3).mean())
S["n_exact_one"] = int((r.rating == 1).sum())
rev_ = df[df.rated & df.has_reviews]
five = rev_[rev_.rating == 5]
S["five_median_reviews"] = float(five.number_of_reviews.median())
S["five_le2_share"] = float((five.number_of_reviews <= 2).mean())
S["five_ge50_n"] = int((five.number_of_reviews >= 50).sum())
S["five_ge100_n"] = int((five.number_of_reviews >= 100).sum())
S["five_ge100_total"] = int((rev_.number_of_reviews >= 100).sum())
S["rating_global_mean_bayes"] = float(M)
S["bayes_C"] = C
bk = rev_.groupby("review_bucket", observed=True).agg(n=("rating", "size"), mean_rating=("rating", "mean"),
                                                      pct5=("rating", lambda s: (s == 5).mean()),
                                                      sd=("rating", "std")).reset_index()
S["bucket_table"] = bk.assign(review_bucket=bk.review_bucket.astype(str)).to_dict("records")
S["spearman_rating_reviews"] = float(rev_[["rating", "number_of_reviews"]].corr(method="spearman").iloc[0, 1])
S["reliable_n"] = int((rev_.number_of_reviews >= 30).sum())
S["reliable_share_of_all"] = float((rev_.number_of_reviews >= 30).sum() / len(df))
S["reliable_mean"] = float(rev_[rev_.number_of_reviews >= 30].rating.mean())
S["reliable_median"] = float(rev_[rev_.number_of_reviews >= 30].rating.median())
S["reliable_five_n"] = int((rev_[rev_.number_of_reviews >= 30].rating == 5).sum())
S["reliable_ge45_n"] = int((rev_[rev_.number_of_reviews >= 30].rating >= 4.5).sum())

# ---- reviews
nr = df.number_of_reviews.dropna()
S["reviews_total"] = int(nr.sum())
S["reviews_mean"] = float(nr.mean())
S["reviews_median"] = float(nr.median())
S["reviews_max"] = int(nr.max())
S["reviews_p90"] = float(nr.quantile(.9))
S["reviews_p99"] = float(nr.quantile(.99))
srt = nr.sort_values(ascending=False)
for q in (0.01, 0.05, 0.10):
    S[f"top{int(q*100)}pct_share_reviews"] = float(srt.iloc[:int(len(srt) * q)].sum() / srt.sum())
S["share_reviews_le10"] = float((nr <= 10).mean())
S["share_reviews_ge100"] = float((nr >= 100).mean())
S["share_reviews_ge1000"] = float((nr >= 1000).mean())
S["n_reviews_ge1000"] = int((nr >= 1000).sum())
lor_x = np.arange(1, len(srt) + 1) / len(srt)
gini_sorted = np.sort(nr.values)
n_ = len(gini_sorted)
S["gini_reviews"] = float((2 * np.sum((np.arange(1, n_ + 1)) * gini_sorted) / (n_ * gini_sorted.sum())) - (n_ + 1) / n_)

# ---- affluence
a = df[df.has_affluence]
aff = a.groupby("affluence").agg(n=("name", "size"), mean_rating=("rating", "mean"), median_reviews=("number_of_reviews", "median"),
                                 mean_reviews=("number_of_reviews", "mean")).reset_index()
S["affluence_table"] = aff.to_dict("records")
S["aff_share_among_labeled"] = {int(k): float(v) for k, v in a.affluence.value_counts(normalize=True).sort_index().items()}
S["aff_labeled_share_by_bucket"] = {str(k): float(v) for k, v in df.groupby("review_bucket", observed=True).has_affluence.mean().items()}
S["spearman_aff_rating"] = float(a[["affluence", "rating"]].corr(method="spearman").iloc[0, 1])
S["spearman_aff_reviews"] = float(a[["affluence", "number_of_reviews"]].corr(method="spearman").iloc[0, 1])
S["aff_dhaka_share"] = float(a.greater_dhaka.mean())
S["aff_by_dhaka"] = a.groupby("greater_dhaka").affluence.mean().to_dict()

# ---- geography
div = bd.groupby("division").agg(n=("name", "size"), rated_n=("rated", "sum"),
                                 unrated_share=("is_unrated", "mean"), mean_rating=("rating", lambda s: s[s > 0].mean()),
                                 median_reviews=("number_of_reviews", "median"),
                                 aff_share=("has_affluence", "mean")).reset_index().sort_values("n", ascending=False)
bay = bd.groupby("division").bayes_rating.mean().rename("mean_bayes")
div = div.merge(bay, on="division")
div["share"] = div.n / div.n.sum()
S["division_table"] = div.to_dict("records")
S["greater_dhaka_n"] = int(df.greater_dhaka.sum())
S["greater_dhaka_share"] = float(df.greater_dhaka.mean())
gd = df[df.greater_dhaka]
S["gd_mean_rating"] = float(gd[gd.rated].rating.mean())
S["rest_mean_rating"] = float(df[~df.greater_dhaka & df.rated].rating.mean())
S["gd_unrated_share"] = float(gd.is_unrated.mean())
S["rest_unrated_share"] = float(df[~df.greater_dhaka].is_unrated.mean())
S["gd_reviews_share"] = float(gd.number_of_reviews.sum() / df.number_of_reviews.sum())
S["gd_median_reviews"] = float(gd.number_of_reviews.median())
S["rest_median_reviews"] = float(df[~df.greater_dhaka].number_of_reviews.median())
S["gd_aff_share"] = float(gd.has_affluence.mean())
S["rest_aff_share"] = float(df[~df.greater_dhaka].has_affluence.mean())
S["gd_aff_n"] = int(gd.has_affluence.sum())
S["india_rows"] = int((df.country == "India").sum())

# ---- names / language
S["bengali_mean_rating"] = float(df[df.bengali_name & df.rated].rating.mean())
S["latin_mean_rating"] = float(df[~df.bengali_name & df.rated].rating.mean())
S["bengali_unrated_share"] = float(df[df.bengali_name].is_unrated.mean())
S["latin_unrated_share"] = float(df[~df.bengali_name].is_unrated.mean())
S["bengali_median_reviews"] = float(df[df.bengali_name].number_of_reviews.median())
S["latin_median_reviews"] = float(df[~df.bengali_name].number_of_reviews.median())
S["bengali_gd_share"] = float(df[df.bengali_name].greater_dhaka.mean())
S["latin_gd_share"] = float(df[~df.bengali_name].greater_dhaka.mean())
kwrows = []
for k in KW:
    m = df["kw_" + k]
    sub = df[m & df.rated & df.has_reviews & (df.number_of_reviews >= 10)]
    kwrows.append(dict(keyword=k, n=int(m.sum()), share=float(m.mean()), mean_rating=float(sub.rating.mean()),
                       median_reviews=float(df[m].number_of_reviews.median()), n_rated10=len(sub)))
kw = pd.DataFrame(kwrows).sort_values("n", ascending=False)
S["keyword_table"] = kw.to_dict("records")
S["any_food_kw_share"] = float(df.any_food_keyword.mean())

# name families (chain / copy-cat proxies)
FAM = {
    "Bismillah": r"bismillah|bishmillah|bismilla|বিসমিল্লাহ|বিছমিল্লাহ",
    "Bhai Bhai / Vai Vai": r"bhai ?bhai|vai ?vai|ভাই ভাই|ভাই-ভাই",
    "Haji Biryani": r"haji.{0,3}biry|hajj?i biriy|হাজী.{0,3}বিরিয়ানি|হাজী.{0,3}বিরিয়ানী",
    "Kazi Farms Kitchen": r"kazi ?farms?",
    "Madina": r"madina|মদিনা",
    "Pizza Hut/Domino's/Pizza Inn": r"pizza hut|domino|pizza inn",
    "KFC": r"\bkfc\b",
    "Star Kebab": r"star kebab|star kabab",
    "Sultan's Dine": r"sultan'?s dine",
    "Nirob / Niribili": r"নিরিবিলি|niribili|nirebili",
}
fam = []
for k, pat in FAM.items():
    m = df.name.str.contains(pat, case=False, regex=True)
    fam.append(dict(family=k, n=int(m.sum()), mean_rating=float(df[m & df.rated].rating.mean()) if (m & df.rated).any() else np.nan))
fam = pd.DataFrame(fam).sort_values("n", ascending=False)
S["family_table"] = fam.to_dict("records")
S["top_exact_names"] = df.name.value_counts().head(10).to_dict()
S["distinct_names"] = int(df.name.nunique())

# ---- top lists
cols = ["name", "rating", "number_of_reviews", "affluence", "division", "address"]
top_rev = df.sort_values("number_of_reviews", ascending=False).head(15)[cols]
top_bayes = df[df.number_of_reviews >= 100].sort_values("bayes_rating", ascending=False).head(15)[cols + ["bayes_rating"]]
worst = df[df.number_of_reviews >= 100].sort_values("bayes_rating").head(10)[cols + ["bayes_rating"]]
S["top_reviews"] = top_rev.to_dict("records")
S["top_bayes"] = top_bayes.to_dict("records")

# =====================================================================
# 4. GRAPHS
# =====================================================================
# 01 data quality overview
fig, ax = plt.subplots(1, 2, figsize=(13, 4.8), gridspec_kw={"width_ratios": [1.1, 1]})
steps = ["Raw rows", "After removing\nexact duplicates", "Unique places\n(by place_id)"]
vals = [S["raw_rows"], S["rows_after_exact_dedup"], S["unique_places"]]
b = ax[0].bar(steps, vals, color=[GRAY, GREEN, GREEN], width=.6)
for rect, v in zip(b, vals):
    ax[0].text(rect.get_x() + rect.get_width() / 2, v + 150, f"{v:,}", ha="center", fontweight="bold")
ax[0].set_title("Duplicates: 15% of rows were repeats"); ax[0].set_ylim(0, 14500); ax[0].grid(axis="x")
miss = {"rating = 0\n(unrated)": S["share_unrated"], "no review\ncount": S["share_no_reviews"],
        "no affluence\n(price level)": 1 - S["share_has_aff"], "plus-code\naddress": S["plus_code_share"],
        "Bengali\nname": S["bengali_name_share"]}
b = ax[1].barh(list(miss)[::-1], [v * 100 for v in list(miss.values())[::-1]], color=[GOLD, GRAY, RED, RED, RED][::-1])
for rect, v in zip(b, list(miss.values())[::-1]):
    ax[1].text(v * 100 + 1, rect.get_y() + rect.get_height() / 2, pct(v), va="center", fontweight="bold")
ax[1].set_xlim(0, 105); ax[1].set_title("Gaps & quirks (% of unique places)"); ax[1].grid(axis="y")
ax[1].xaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x:.0f}%"))
fig.tight_layout(); save("01_data_quality_overview.png", fig)

# 02 rating distribution
fig, ax = plt.subplots(figsize=(11, 5))
vc = df.rating.round(1).value_counts().sort_index()
colors = [GRAY if i == 0 else (RED if i == 5 else GREEN) for i in vc.index]
ax.bar(vc.index, vc.values, width=0.085, color=colors)
ax.set_xlabel("Rating (0 = no rating yet)"); ax.set_ylabel("Number of places")
ax.set_title("Ratings pile up at 4.0 - and at a suspicious perfect 5.0")
ax.annotate(f"{S['n_unrated']:,} unrated\n({pct(S['share_unrated'],0)})", (0, vc[0]), xytext=(0.35, vc[0] * .85), color=DARK, fontsize=10,
            arrowprops=dict(arrowstyle="-", color=GRAY))
ax.annotate(f"{S['n_five']:,} perfect 5.0\n(mostly 1-2 reviews)", (5, vc[5.0]), xytext=(3.6, vc[5.0] * 1.02), color=RED, fontsize=10, ha="right")
ax.annotate(f"4.0 = biggest genuine peak\n({vc[4.0]:,} places)", (4.0, vc[4.0]), xytext=(3.55, vc[4.0] * 1.15), color=GREEN, fontsize=10, ha="right")
fig.tight_layout(); save("02_rating_distribution.png", fig)

# 03 review distribution
fig, ax = plt.subplots(1, 2, figsize=(13, 4.8))
ax[0].hist(nr, bins=np.logspace(0, np.log10(nr.max() + 1), 40), color=GREEN, edgecolor="white")
ax[0].set_xscale("log"); ax[0].set_xlabel("Number of reviews (log scale)"); ax[0].set_ylabel("Places")
ax[0].axvline(nr.median(), color=RED, ls="--"); ax[0].text(nr.median() * 1.15, ax[0].get_ylim()[1] * .9, f"median = {nr.median():.0f}", color=RED)
ax[0].set_title("Most places have very few reviews")
ranges = ["1-10", "11-99", "100-999", "1000+"]
cnts = [((nr <= 10)).sum(), ((nr > 10) & (nr < 100)).sum(), ((nr >= 100) & (nr < 1000)).sum(), (nr >= 1000).sum()]
b = ax[1].bar(ranges, cnts, color=[GRAY, GREEN, GREEN, RED])
for rect, v in zip(b, cnts):
    ax[1].text(rect.get_x() + rect.get_width() / 2, v + 40, f"{v:,}\n({pct(v/len(nr),0)})", ha="center", fontsize=10)
ax[1].set_ylim(0, max(cnts) * 1.18); ax[1].set_title("Places by review volume"); ax[1].grid(axis="x"); ax[1].set_xlabel("Reviews per place")
fig.tight_layout(); save("03_review_count_distribution.png", fig)

# 04 rating vs reviews (small-sample effect)
fig, ax = plt.subplots(1, 2, figsize=(13, 5))
sc = rev_.sample(min(5000, len(rev_)), random_state=3)
ax[0].scatter(sc.number_of_reviews, sc.rating + np.random.default_rng(1).normal(0, .03, len(sc)), s=6, alpha=.25, color=GREEN)
ax[0].set_xscale("log"); ax[0].set_xlabel("Number of reviews (log)"); ax[0].set_ylabel("Rating"); ax[0].set_title("Ratings settle down as reviews grow")
ax[0].set_ylim(0.8, 5.2)
ax[1].bar(bk.review_bucket.astype(str), bk.sd, color=GOLD)
ax[1].set_ylabel("Spread of ratings (std dev)"); ax[1].set_xlabel("Reviews per place"); ax[1].set_title("Rating spread collapses with more reviews")
for i, v in enumerate(bk.sd):
    ax[1].text(i, v + .02, f"{v:.2f}", ha="center", fontsize=10)
ax[1].grid(axis="x")
fig.tight_layout(); save("04_rating_vs_review_count.png", fig)

# 05 five-star illusion
fig, ax = plt.subplots(1, 2, figsize=(13, 4.8))
b = ax[0].bar(bk.review_bucket.astype(str), bk.pct5 * 100, color=[RED if v > .2 else GREEN for v in bk.pct5])
for rect, v in zip(b, bk.pct5):
    ax[0].text(rect.get_x() + rect.get_width() / 2, v * 100 + 1, pct(v, 1), ha="center", fontsize=10, fontweight="bold")
ax[0].set_title("Share of places with a PERFECT 5.0"); ax[0].set_xlabel("Reviews per place"); ax[0].set_ylabel("% of places"); ax[0].grid(axis="x")
ax[0].yaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x:.0f}%"))
ax[1].bar(bk.review_bucket.astype(str), bk.mean_rating, color=GREEN)
for i, v in enumerate(bk.mean_rating):
    ax[1].text(i, v + .03, f"{v:.2f}", ha="center", fontsize=10, fontweight="bold")
ax[1].set_ylim(3, 5); ax[1].set_title("Average rating by review volume"); ax[1].set_xlabel("Reviews per place"); ax[1].grid(axis="x")
fig.tight_layout(); save("05_five_star_illusion.png", fig)

# 06 review concentration (Lorenz)
fig, ax = plt.subplots(figsize=(7.5, 6))
asc = np.sort(nr.values)
cum = np.cumsum(asc) / asc.sum(); x = np.arange(1, len(asc) + 1) / len(asc)
ax.plot(np.r_[0, x], np.r_[0, cum], color=GREEN, lw=3, label="Actual reviews")
ax.plot([0, 1], [0, 1], color=GRAY, ls="--", label="If every place had equal reviews")
ax.fill_between(np.r_[0, x], np.r_[0, cum], np.r_[0, x], color=GREEN, alpha=.12)
ax.set_xlabel("Cumulative share of places (fewest -> most reviews)"); ax.set_ylabel("Cumulative share of all reviews")
ax.set_title(f"A few places hold most reviews (Gini = {S['gini_reviews']:.2f})")
ax.text(.05, .85, f"Top 1% of places: {pct(S['top1pct_share_reviews'],0)} of reviews\nTop 10% of places: {pct(S['top10pct_share_reviews'],0)} of reviews", fontsize=11,
        bbox=dict(boxstyle="round", fc="white", ec=GRAY))
ax.legend(loc="lower right"); ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0%}")); ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0%}"))
fig.tight_layout(); save("06_review_concentration.png", fig)

# 07 affluence
fig, ax = plt.subplots(1, 3, figsize=(14, 4.6))
lbl = ["1\n(lowest)", "2", "3", "4\n(highest)"]
ax[0].bar(lbl, aff.n, color=GREEN)
for i, v in enumerate(aff.n):
    ax[0].text(i, v + 15, f"{v:,}\n({pct(v/aff.n.sum(),0)})", ha="center", fontsize=10)
ax[0].set_ylim(0, aff.n.max() * 1.2); ax[0].set_title("Places per affluence level"); ax[0].grid(axis="x")
ax[1].bar(lbl, aff.mean_rating, color=GOLD)
for i, v in enumerate(aff.mean_rating):
    ax[1].text(i, v + .02, f"{v:.2f}", ha="center", fontsize=10, fontweight="bold")
ax[1].set_ylim(3, 4.6); ax[1].set_title("Average rating"); ax[1].grid(axis="x")
ax[2].bar(lbl, aff.median_reviews, color=RED)
for i, v in enumerate(aff.median_reviews):
    ax[2].text(i, v + 15, f"{v:.0f}", ha="center", fontsize=10, fontweight="bold")
ax[2].set_title("Median reviews"); ax[2].grid(axis="x"); ax[2].set_ylim(0, aff.median_reviews.max() * 1.18)
fig.suptitle("Affluence level (1-4), only available for places with reviews", x=0.01, ha="left", fontweight="bold", fontsize=14)
fig.tight_layout(); save("07_affluence_levels.png", fig)

# 08 affluence availability by review bucket
fig, ax = plt.subplots(figsize=(9.5, 4.8))
s8 = df.groupby("review_bucket", observed=True).has_affluence.mean() * 100
b = ax.bar(s8.index.astype(str), s8.values, color=GREEN)
for rect, v in zip(b, s8.values):
    ax.text(rect.get_x() + rect.get_width() / 2, v + 1, f"{v:.0f}%", ha="center", fontweight="bold")
ax.set_ylim(0, 100); ax.set_xlabel("Reviews per place"); ax.set_ylabel("% of places with an affluence value")
ax.set_title("Affluence is missing for low-review places - not random"); ax.grid(axis="x")
fig.tight_layout(); save("08_affluence_availability.png", fig)

# 09 map - all places (Bangladesh)
fig, ax = plt.subplots(1, 2, figsize=(14, 7.2))
b_ = df[df.country == "Bangladesh"]
ax[0].hexbin(b_.longitude, b_.latitude, gridsize=55, cmap="Greens", mincnt=1, bins="log")
ax[0].set_title("Where the places are (hex density, log scale)")
rr = b_[b_.rated]
sc = ax[1].scatter(rr.longitude, rr.latitude, c=rr.rating, cmap="RdYlGn", s=4, alpha=.6, vmin=2, vmax=5)
plt.colorbar(sc, ax=ax[1], shrink=.7, label="Rating")
ax[1].set_title("Individual rated places, coloured by rating")
for a_ in ax:
    a_.set_xlabel("Longitude"); a_.set_ylabel("Latitude"); a_.set_aspect("equal"); a_.grid(False)
    a_.plot(90.40, 23.78, marker="*", color=RED, ms=0)
ax[0].annotate("Dhaka", (90.40, 23.78), xytext=(91.0, 24.6), arrowprops=dict(arrowstyle="->", color=RED), color=RED, fontweight="bold")
ax[0].annotate("Chattogram", (91.80, 22.35), xytext=(91.9, 23.1), arrowprops=dict(arrowstyle="->", color=RED), color=RED, fontweight="bold")
fig.tight_layout(); save("09_map_all_places.png", fig)

# 10 Dhaka zoom
fig, ax = plt.subplots(1, 2, figsize=(14, 6.5))
z = df[(df.latitude.between(23.65, 23.92)) & (df.longitude.between(90.30, 90.52))]
h = ax[0].hexbin(z.longitude, z.latitude, gridsize=40, cmap="YlOrRd", mincnt=1)
plt.colorbar(h, ax=ax[0], shrink=.8, label="Places per hex"); ax[0].set_title(f"Dhaka core: {len(z):,} places")
zr = z[z.rated & z.has_reviews & (z.number_of_reviews >= 10)]
h2 = ax[1].hexbin(zr.longitude, zr.latitude, C=zr.rating, reduce_C_function=np.mean, gridsize=30, cmap="RdYlGn", vmin=3.3, vmax=4.6, mincnt=3)
plt.colorbar(h2, ax=ax[1], shrink=.8, label="Avg rating (hexes with 3+ places, 10+ reviews each)"); ax[1].set_title("Average rating by area")
for a_ in ax:
    a_.set_aspect("equal"); a_.grid(False); a_.set_xlabel("Longitude"); a_.set_ylabel("Latitude")
fig.tight_layout(); save("10_map_dhaka_zoom.png", fig)

# 11 division comparison
fig, ax = plt.subplots(1, 3, figsize=(15, 5), sharey=True)
dv = div.sort_values("n")
ax[0].barh(dv.division, dv.n, color=GREEN)
for i, (v, s_) in enumerate(zip(dv.n, dv.share)):
    ax[0].text(v + 30, i, f"{v:,} ({pct(s_,0)})", va="center", fontsize=9)
ax[0].set_xlim(0, dv.n.max() * 1.35); ax[0].set_title("Places"); ax[0].grid(axis="y")
ax[1].barh(dv.division, dv.unrated_share * 100, color=GOLD)
for i, v in enumerate(dv.unrated_share):
    ax[1].text(v * 100 + .5, i, pct(v, 0), va="center", fontsize=9)
ax[1].set_xlim(0, dv.unrated_share.max() * 100 * 1.25); ax[1].set_title("% unrated"); ax[1].grid(axis="y")
ax[2].barh(dv.division, dv.mean_rating, color=RED)
for i, v in enumerate(dv.mean_rating):
    ax[2].text(v + .01, i, f"{v:.2f}", va="center", fontsize=9)
ax[2].set_xlim(3.4, dv.mean_rating.max() + .35); ax[2].set_title("Avg rating (rated places)"); ax[2].grid(axis="y")
fig.suptitle("Divisions compared (nearest-place geocoding; Dhaka includes Mymensingh division)", x=.01, ha="left", fontweight="bold", fontsize=13)
fig.tight_layout(); save("11_divisions_compared.png", fig)

# 12 Dhaka vs rest
fig, ax = plt.subplots(1, 4, figsize=(15, 4.4))
pairs = [("Share of places", [S["greater_dhaka_share"] * 100, (1 - S["greater_dhaka_share"]) * 100], "%"),
         ("Median reviews", [S["gd_median_reviews"], S["rest_median_reviews"]], ""),
         ("% with affluence value", [S["gd_aff_share"] * 100, S["rest_aff_share"] * 100], "%"),
         ("Avg rating", [S["gd_mean_rating"], S["rest_mean_rating"]], "")]
for a_, (t, v, u) in zip(ax, pairs):
    b = a_.bar(["Greater\nDhaka", "Rest of\ncountry"], v, color=[RED, GREEN], width=.6)
    for rect, x in zip(b, v):
        a_.text(rect.get_x() + rect.get_width() / 2, x * 1.01, f"{x:.1f}{u}" if t != "Avg rating" else f"{x:.2f}", ha="center", fontweight="bold")
    a_.set_title(t); a_.grid(axis="x"); a_.set_ylim(0, max(v) * 1.18) if t != "Avg rating" else a_.set_ylim(3, 4.4)
fig.suptitle("Greater Dhaka (within 20 km of centre) vs the rest of Bangladesh", x=.01, ha="left", fontweight="bold", fontsize=13)
fig.tight_layout(); save("12_dhaka_vs_rest.png", fig)

# 13 name keywords
fig, ax = plt.subplots(1, 2, figsize=(14, 5), sharey=True)
k2 = kw.sort_values("n")
ax[0].barh(k2.keyword, k2.n, color=GREEN)
for i, v in enumerate(k2.n):
    ax[0].text(v + 40, i, f"{v:,}", va="center", fontsize=9)
ax[0].set_title("Places with the keyword in the name"); ax[0].set_xlim(0, k2.n.max() * 1.15); ax[0].grid(axis="y")
ax[1].barh(k2.keyword, k2.mean_rating, color=GOLD)
for i, (v, n_) in enumerate(zip(k2.mean_rating, k2.n_rated10)):
    ax[1].text(v + .005, i, f"{v:.2f}  (n={n_})", va="center", fontsize=9)
ax[1].set_xlim(3.4, 4.35); ax[1].set_title("Avg rating (places with 10+ reviews)"); ax[1].grid(axis="y")
fig.tight_layout(); save("13_name_keywords.png", fig)

# 14 language
fig, ax = plt.subplots(1, 4, figsize=(15, 4.4))
L = [("Share of places", [S["bengali_name_share"] * 100, (1 - S["bengali_name_share"]) * 100], "%"),
     ("% unrated", [S["bengali_unrated_share"] * 100, S["latin_unrated_share"] * 100], "%"),
     ("Median reviews", [S["bengali_median_reviews"], S["latin_median_reviews"]], ""),
     ("% in Greater Dhaka", [S["bengali_gd_share"] * 100, S["latin_gd_share"] * 100], "%")]
for a_, (t, v, u) in zip(ax, L):
    b = a_.bar(["Bengali\nname", "Latin\nname"], v, color=[RED, GREEN], width=.6)
    for rect, x in zip(b, v):
        a_.text(rect.get_x() + rect.get_width() / 2, x * 1.01, f"{x:.0f}{u}", ha="center", fontweight="bold")
    a_.set_title(t); a_.grid(axis="x"); a_.set_ylim(0, max(v) * 1.2)
fig.suptitle("Bengali-script vs Latin-script place names", x=.01, ha="left", fontweight="bold", fontsize=13)
fig.tight_layout(); save("14_language_of_names.png", fig)

# 15 top places (latin names only for font support)
lat = ~df.bengali_name
t1 = df[lat].sort_values("number_of_reviews", ascending=False).drop_duplicates("name").head(12)
t2 = df[lat & (df.number_of_reviews >= 500)].sort_values("bayes_rating", ascending=False).drop_duplicates("name").head(12)
fig, ax = plt.subplots(1, 2, figsize=(15, 5.8))
t1s = t1.iloc[::-1]
ax[0].barh([n[:32] for n in t1s.name], t1s.number_of_reviews, color=GREEN)
for i, (v, rt) in enumerate(zip(t1s.number_of_reviews, t1s.rating)):
    ax[0].text(v + 150, i, f"{v:,.0f}  ({rt:.1f}*)", va="center", fontsize=9)
ax[0].set_xlim(0, t1.number_of_reviews.max() * 1.25); ax[0].set_title("Most-reviewed places"); ax[0].grid(axis="y")
t2s = t2.iloc[::-1]
ax[1].barh([n[:32] for n in t2s.name], t2s.bayes_rating, color=RED)
for i, (v, rt, nn) in enumerate(zip(t2s.bayes_rating, t2s.rating, t2s.number_of_reviews)):
    ax[1].text(v + .003, i, f"{v:.2f}  ({rt:.1f}* / {nn:,.0f})", va="center", fontsize=9)
ax[1].set_xlim(t2.bayes_rating.min() - .1, t2.bayes_rating.max() + .22); ax[1].set_title("Best-rated places with 500+ reviews (adjusted score)"); ax[1].grid(axis="y")
fig.text(.01, -.02, "Latin-script names only (no Bengali font available for charts). Adjusted score shrinks ratings toward the global mean; label = raw rating / reviews.", fontsize=9, color=GRAY)
fig.tight_layout(); save("15_top_places.png", fig)

# 16 name families
f2 = fam.sort_values("n")
fig, ax = plt.subplots(figsize=(10, 5))
ax.barh(f2.family, f2.n, color=GREEN)
for i, (v, rt) in enumerate(zip(f2.n, f2.mean_rating)):
    ax.text(v + 1, i, f"{v}  (avg {rt:.2f}*)" if not np.isnan(rt) else f"{v}", va="center", fontsize=9)
ax.set_xlim(0, f2.n.max() * 1.25); ax.set_title("Repeated names: likely chains or copy-cat naming"); ax.grid(axis="y")
fig.tight_layout(); save("16_name_families.png", fig)

# 17 data-cleanliness funnel: how many places can we trust for rating analysis
fig, ax = plt.subplots(figsize=(10, 4.8))
fun = [("All unique places", len(df)), ("Have a rating (> 0)", int(df.rated.sum())),
       ("Rated + 10+ reviews", int((rev_.number_of_reviews >= 10).sum())),
       ("Rated + 30+ reviews", int((rev_.number_of_reviews >= 30).sum())),
       ("Rated + 100+ reviews", int((rev_.number_of_reviews >= 100).sum()))]
b = ax.barh([f[0] for f in fun][::-1], [f[1] for f in fun][::-1], color=[RED, GREEN, GREEN, GREEN, GRAY][::-1][::-1][::-1])
for rect, (_, v) in zip(b, fun[::-1]):
    ax.text(v + 80, rect.get_y() + rect.get_height() / 2, f"{v:,}  ({pct(v/len(df),0)})", va="center", fontweight="bold")
ax.set_xlim(0, len(df) * 1.22); ax.set_title("How many places have enough data to trust?"); ax.grid(axis="y")
S["funnel"] = fun
fig.tight_layout(); save("17_trustworthy_data_funnel.png", fig)

# =====================================================================
# 5. FACT FILES
# =====================================================================
def w(name, lines):
    with open(os.path.join(F, name), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


H = lambda t: ["=" * 70, t, "=" * 70]
w("01_dataset_overview.txt", H("DATASET OVERVIEW") + [
    f"File: restaurants.csv",
    f"Raw rows: {S['raw_rows']:,}      Columns: {len(S['raw_cols'])}  ({', '.join(S['raw_cols'])})",
    f"Unique places after cleaning: {S['unique_places']:,}",
    "",
    "COLUMN GUIDE",
    " place_id          Google Maps-style unique ID (ChIJ...)",
    " name              Business name (Bengali or Latin script, sometimes mixed)",
    " latitude/longitude  Coordinates",
    " rating            1.0-5.0 star rating; 0 = no rating yet (see data quality)",
    " number_of_reviews How many reviews back the rating (blank if none)",
    " affluence         Integer 1-4, looks like a price/affluence level (1 = lowest, 4 = highest).",
    "                   Meaning is inferred - there is no data dictionary.",
    " address           Free text; often a Plus Code (e.g. 7XP4+9WW) or road/area name",
    "",
    f"Geographic span: lat {S['lat_range'][0]:.2f} to {S['lat_range'][1]:.2f}, lon {S['lon_range'][0]:.2f} to {S['lon_range'][1]:.2f}",
    f"Places in Bangladesh: {S['country_counts'].get('Bangladesh',0):,}   |  Border places listed with Indian addresses: {S['india_rows']}",
    f"Total reviews across all places: {S['reviews_total']:,}",
])

w("02_data_quality_issues.txt", H("DATA QUALITY ISSUES FOUND (and what we did)") + [
    f"1. DUPLICATES: {S['exact_dup_rows']:,} rows ({pct(S['exact_dup_rows']/S['raw_rows'])}) were exact copies of another row.",
    f"   {S['places_repeated']:,} places appear more than once; one place appears {S['max_copies']} times.",
    f"   FIX: removed exact duplicates -> {S['rows_after_exact_dedup']:,} rows.",
    f"   {S['conflicting_dup_ids']} place_ids still had 2 rows with slightly different review counts (scrape timing).",
    f"   FIX: kept the row with the larger review count -> {S['unique_places']:,} unique places.",
    "",
    f"2. RATING = 0 MEANS 'NO RATING': {S['n_unrated']:,} places ({pct(S['share_unrated'])}) have rating 0.",
    f"   All of them have no review count: {S['unrated_all_no_reviews']}. A real 0-star rating does not exist on this scale.",
    "   FIX: treated 0 as missing for all rating statistics (including it would drag the mean down to "
    f"{df.rating.mean():.2f} instead of {S['rating_mean']:.2f}).",
    f"   {S['rated_but_no_reviews']} places have a rating but no review count (left in, excluded from review-based stats).",
    "",
    f"3. REVIEW COUNT BLANK: {S['n_no_reviews']:,} places ({pct(S['share_no_reviews'])}) - same group as the unrated places.",
    "",
    f"4. AFFLUENCE MOSTLY MISSING: only {S['n_has_aff']:,} places ({pct(S['share_has_aff'])}) have a value.",
    f"   The smallest review count among places that have affluence is {S['aff_min_reviews']:.0f}; none are unrated. It is NOT missing at random:",
    "   it only appears for places with enough reviews. Averages by affluence describe popular places only.",
    "",
    f"5. NOT EVERYTHING IS A RESTAURANT: ~{S['non_rest_n']} places ({pct(S['non_rest_share'])}) have names that look like stores, telecom shops,",
    "   schools, farms, etc. (conservative keyword check - true number is likely higher, since personal names and",
    f"   unusual names can't be detected). {S['short_names']} places have names of 3 characters or fewer (e.g. 'Gg', 'bk', 'no').",
    "   FIX: flagged in data/restaurants_clean.csv (column likely_non_restaurant), not deleted.",
    "",
    f"6. OUTSIDE BANGLADESH: {S['india_rows']} places have Indian addresses (Tripura, West Bengal, Assam border towns).",
    "   FIX: flagged (column country) and excluded from division-level geographic analysis.",
    "",
    f"7. MIXED LANGUAGES: {S['bengali_name_n']:,} names ({pct(S['bengali_name_share'])}) are in Bengali script. The same business can appear under",
    "   different spellings (Bismillah / Bishmillah / বিসমিল্লাহ), so name matching needs both scripts.",
    "",
    f"8. ADDRESSES ARE MESSY: {S['plus_code_n']:,} ({pct(S['plus_code_share'])}) are just Plus Codes; {S['unnamed_road_n']} say 'Unnamed Road'.",
    "   There is no clean city/district column - division was derived from coordinates (offline reverse geocoder).",
    "   Mymensingh division is merged into Dhaka in that geodata (it uses the older 7-division map).",
])

fv = bk.set_index(bk.review_bucket.astype(str))
w("03_rating_facts.txt", H("RATING FACTS") + [
    f"Rated places: {S['n_rated']:,}  (mean {S['rating_mean']:.2f}, median {S['rating_median']:.1f}, mode {S['rating_mode']:.1f})",
    f"Places rated 4.0 or higher: {S['n_four_plus']:,} ({pct(S['share_four_plus'])} of rated)",
    f"Places rated below 3.0: {S['n_below3']:,} ({pct(S['share_below3'])})",
    f"Perfect 5.0: {S['n_five']:,} ({pct(S['share_five_of_rated'])} of rated) - the single most common rating, ahead of 4.0 ({int((r.rating==4.0).sum()):,} places)",
    f"   Of the perfect-5.0 places that have a review count: {pct(S['five_le2_share'],0)} have only 1-2 reviews (median {S['five_median_reviews']:.0f}).",
    f"   No perfect-5.0 place has more than {int(five.number_of_reviews.max())} reviews. Among {S['five_ge100_total']:,} places with 100+ reviews, the highest rating is {rev_[rev_.number_of_reviews>=100].rating.max():.1f}.",
    "",
    "THE SMALL-SAMPLE EFFECT (ratings by number of reviews)",
    "  reviews     places    avg rating   % perfect 5.0   rating std-dev",
] + [f"  {k:<9} {int(r_.n):>7,}     {r_.mean_rating:.2f}          {pct(r_.pct5):>6}          {r_.sd:.2f}" for k, r_ in fv.iterrows()] + [
    "",
    f"Spearman correlation rating vs review count: {S['spearman_rating_reviews']:.2f} (weak NEGATIVE - places with more reviews tend to have LOWER, more realistic ratings; few-review places are inflated by 5.0s).",
    "",
    "TRUSTWORTHY SUBSET (rating + 30 or more reviews)",
    f"  {S['reliable_n']:,} places ({pct(S['reliable_share_of_all'])} of all places): mean {S['reliable_mean']:.2f}, median {S['reliable_median']:.1f}",
    f"  Of these {S['reliable_five_n']} are a perfect 5.0 and {S['reliable_ge45_n']} are 4.5+.",
    "",
    f"ADJUSTED SCORE: bayes = (v*R + {C}*{M:.2f}) / (v + {C}), where v = reviews, R = rating. Pulls low-review ratings toward the global mean",
    "  so a 5.0 from 1 review no longer beats a 4.6 from 3,000 reviews. See facts/08_top_lists.txt.",
])

w("04_reviews_popularity_facts.txt", H("REVIEW / POPULARITY FACTS") + [
    f"Total reviews: {S['reviews_total']:,} across {len(nr):,} places with at least one review",
    f"Mean {S['reviews_mean']:.0f} reviews per place  vs  median {S['reviews_median']:.0f}   (huge gap = very skewed)",
    f"90th percentile: {S['reviews_p90']:.0f}    99th percentile: {S['reviews_p99']:.0f}    max: {S['reviews_max']:,}",
    f"{pct(S['share_reviews_le10'],0)} of places with reviews have 10 or fewer; {pct(S['share_reviews_ge100'],0)} have 100+; only {S['n_reviews_ge1000']} ({pct(S['share_reviews_ge1000'])}) have 1,000+",
    "",
    "CONCENTRATION",
    f"Top 1% of places hold {pct(S['top1pct_share_reviews'])} of all reviews",
    f"Top 5% hold {pct(S['top5pct_share_reviews'])}    |    Top 10% hold {pct(S['top10pct_share_reviews'])}",
    f"Gini coefficient of reviews: {S['gini_reviews']:.2f}  (0 = perfectly equal, 1 = one place has everything)",
    "",
    f"Greater Dhaka holds {pct(S['greater_dhaka_share'],0)} of places but {pct(S['gd_reviews_share'],0)} of all reviews.",
    "Interpretation: reviews measure visibility/footfall, not just quality. A place with 17k reviews and 3.5 stars is",
    "very well known, not necessarily good.",
])

w("05_affluence_facts.txt", H("AFFLUENCE FACTS") + [
    "Affluence is an integer 1-4. It is probably a price level (1 = cheap ... 4 = expensive) but this is an assumption.",
    f"Only {S['n_has_aff']:,} places ({pct(S['share_has_aff'])}) have it, and only places with {S['aff_min_reviews']:.0f}+ reviews.",
    "",
    "  level   places   share    avg rating   median reviews",
] + [f"  {int(r_.affluence)}      {int(r_.n):>6,}   {pct(r_.n / aff.n.sum()):>6}     {r_.mean_rating:.2f}        {r_.median_reviews:.0f}" for _, r_ in aff.iterrows()] + [
    "",
    f"Level 2 dominates ({pct(S['aff_share_among_labeled'][2],0)}); level 4 is rare ({int(aff[aff.affluence==4].n.iloc[0])} places).",
    f"Rating rises slightly with affluence ({aff.mean_rating.iloc[0]:.2f} at level 1 -> {aff.mean_rating.iloc[3]:.2f} at level 4), but levels 3-4 have few places so be careful.",
    f"Spearman correlation affluence vs rating: {S['spearman_aff_rating']:.2f};  affluence vs reviews: {S['spearman_aff_reviews']:.2f}",
    f"{pct(S['aff_dhaka_share'],0)} of places with an affluence value are in Greater Dhaka (vs {pct(S['greater_dhaka_share'],0)} of all places).",
    "",
    "Share of places that HAVE an affluence value, by review bucket:",
] + [f"   {k:<8} {pct(v,0)}" for k, v in S["aff_labeled_share_by_bucket"].items()] + [
    "Caution: any 'affluence' conclusion applies to well-reviewed places only.",
])

w("06_geography_facts.txt", H("GEOGRAPHY FACTS") + [
    f"{S['country_counts'].get('Bangladesh',0):,} places in Bangladesh; {S['india_rows']} just across the border in India.",
    f"Greater Dhaka (within 20 km of centre): {S['greater_dhaka_n']:,} places = {pct(S['greater_dhaka_share'])} of the dataset",
    f"  avg rating {S['gd_mean_rating']:.2f} vs {S['rest_mean_rating']:.2f} elsewhere;  unrated: {pct(S['gd_unrated_share'],0)} vs {pct(S['rest_unrated_share'],0)} elsewhere",
    f"  median reviews {S['gd_median_reviews']:.0f} vs {S['rest_median_reviews']:.0f};  has affluence value: {pct(S['gd_aff_share'],0)} vs {pct(S['rest_aff_share'],0)}",
    "",
    "BY DIVISION (derived from coordinates; Dhaka includes Mymensingh)",
    "  division      places   share   unrated   avg rating   median reviews",
] + [f"  {r_.division:<12} {int(r_.n):>6,}  {pct(r_.share,0):>5}   {pct(r_.unrated_share,0):>5}      {r_.mean_rating:.2f}        {r_.median_reviews:.0f}" for _, r_ in div.iterrows()] + [
    "",
    "Reading: the unrated share is much higher outside the big cities - rural listings exist on the map but",
    "few people have reviewed them. Ratings outside Dhaka are therefore based on thinner evidence.",
])

w("07_names_and_categories_facts.txt", H("NAMES & CATEGORY FACTS") + [
    f"{S['distinct_names']:,} distinct names among {S['unique_places']:,} places.",
    f"{pct(S['any_food_kw_share'],0)} of names contain an obvious food keyword (English or Bengali).",
    "",
    "KEYWORD GROUPS (a place can be in more than one)",
    "  group                     places   share   avg rating (10+ reviews)   median reviews",
] + [f"  {r_.keyword:<24} {int(r_.n):>6,}  {pct(r_.share,1):>5}        {r_.mean_rating:.2f} (n={int(r_.n_rated10)})              {r_.median_reviews:.0f}" for _, r_ in kw.iterrows()] + [
    "",
    "NAME FAMILIES (possible chains / popular naming)",
] + [f"  {r_.family:<30} {int(r_.n):>4} places  avg rating {r_.mean_rating:.2f}" for _, r_ in fam.iterrows()] + [
    "",
    "MOST COMMON EXACT NAMES",
] + [f"  {n}  x{c}" for n, c in S["top_exact_names"].items()] + [
    "",
    "LANGUAGE",
    f"  Bengali-script names: {S['bengali_name_n']:,} ({pct(S['bengali_name_share'])}); avg rating {S['bengali_mean_rating']:.2f} vs {S['latin_mean_rating']:.2f} for Latin",
    f"  Unrated: {pct(S['bengali_unrated_share'],0)} (Bengali) vs {pct(S['latin_unrated_share'],0)} (Latin); median reviews {S['bengali_median_reviews']:.0f} vs {S['latin_median_reviews']:.0f}",
    f"  In Greater Dhaka: {pct(S['bengali_gd_share'],0)} of Bengali-named places vs {pct(S['latin_gd_share'],0)} of Latin-named",
])


def fmt_row(r_, extra=""):
    nr_ = "n/a" if pd.isna(r_.number_of_reviews) else f"{r_.number_of_reviews:,.0f}"
    af = "-" if pd.isna(r_.affluence) else f"{int(r_.affluence)}"
    return f"  {r_['name'][:45]:<45} {r_.rating:.1f}*  {nr_:>7} reviews  aff {af}  {r_.division}{extra}"


w("08_top_lists.txt", H("TOP LISTS") + ["", "TOP 15 MOST-REVIEWED PLACES"] + [fmt_row(r_) for _, r_ in top_rev.iterrows()] + [
    "", f"TOP 15 BY ADJUSTED RATING (100+ reviews only; adjusted for review count)"] + [fmt_row(r_, f"  adj {r_.bayes_rating:.2f}") for _, r_ in top_bayes.iterrows()] + [
    "", "BOTTOM 10 BY ADJUSTED RATING (100+ reviews)"] + [fmt_row(r_, f"  adj {r_.bayes_rating:.2f}") for _, r_ in worst.iterrows()])

# ---------- key takeaways ----------
tk = [
    f"1. The file has {S['raw_rows']:,} rows but only {S['unique_places']:,} unique places - {pct(S['exact_dup_rows']/S['raw_rows'],0)} of rows were exact duplicates.",
    f"2. {pct(S['share_unrated'],0)} of places ({S['n_unrated']:,}) have no rating (stored as 0) and no reviews. Treat 0 as 'missing', never as a score.",
    f"3. Among rated places the average is {S['rating_mean']:.2f}; the most common rating is {S['rating_mode']:.1f}. Ratings are generous: {pct(S['share_four_plus'],0)} are 4.0+.",
    f"4. {S['n_five']:,} places have a perfect 5.0, but {pct(S['five_le2_share'],0)} of those have only 1-2 reviews. No 5.0 place has more than 20 reviews.",
    f"5. Reviews are extremely concentrated: the top 1% of places hold {pct(S['top1pct_share_reviews'],0)} of all reviews; the median place has just {S['reviews_median']:.0f}.",
    f"6. Only {S['reliable_n']:,} places ({pct(S['reliable_share_of_all'],0)}) combine a rating with 30+ reviews - that is the trustworthy core of the dataset.",
    f"7. Affluence (1-4) exists for only {pct(S['share_has_aff'],0)} of places and only for those with {S['aff_min_reviews']:.0f}+ reviews. Level 2 is {pct(S['aff_share_among_labeled'][2],0)} of the labelled places.",
    f"8. Greater Dhaka has {pct(S['greater_dhaka_share'],0)} of places and {pct(S['gd_reviews_share'],0)} of all reviews. Outside the big cities many listings are unrated.",
    f"9. About {pct(S['bengali_name_share'],0)} of names are in Bengali script; ~{pct(S['non_rest_share'],0)} look like non-restaurants (stores, shops, etc.).",
    "10. Recommended handling: dedupe by place_id, treat rating 0 as missing, use an adjusted (Bayesian) rating or a minimum-review filter, and never compare affluence levels without remembering they only cover popular places.",
]
w("09_key_takeaways.txt", H("KEY TAKEAWAYS") + tk)
S["takeaways"] = tk

# =====================================================================
# 6. SAVE CLEAN DATA + STATS
# =====================================================================
keep = ["place_id", "name", "latitude", "longitude", "rating", "number_of_reviews", "affluence", "address", "country", "division",
        "greater_dhaka", "km_from_dhaka", "is_unrated", "has_affluence", "bengali_name", "likely_non_restaurant", "review_bucket", "bayes_rating"]
df[keep].to_csv(os.path.join(D, "restaurants_clean.csv"), index=False, encoding="utf-8")


def conv(o):
    if isinstance(o, (np.integer,)): return int(o)
    if isinstance(o, (np.floating,)): return None if np.isnan(o) else float(o)
    if isinstance(o, (np.bool_,)): return bool(o)
    return str(o)


with open(os.path.join(OUT, "stats.json"), "w", encoding="utf-8") as fh:
    json.dump(S, fh, default=conv, ensure_ascii=False, indent=1)
print("done:", len(os.listdir(G)), "graphs,", len(os.listdir(F)), "fact files")
print("\n".join(tk))
