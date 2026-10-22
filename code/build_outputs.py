"""Builds presentation_script.md and deck_data.json from stats.json + cleaned data."""
import json, os
import pandas as pd

OUT = os.path.dirname(os.path.abspath(__file__))
S = json.load(open(os.path.join(OUT, "stats.json"), encoding="utf-8"))
df = pd.read_csv(os.path.join(OUT, "data", "restaurants_clean.csv"))

p0 = lambda x: f"{100*x:.0f}%"
p1 = lambda x: f"{100*x:.1f}%"
n = lambda x: f"{int(round(x)):,}"

uniq, raw = S["unique_places"], S["raw_rows"]
bt = {r["review_bucket"]: r for r in S["bucket_table"]}
div = S["division_table"]
dhaka = next(d for d in div if d["division"] == "Dhaka")
aff = {int(a["affluence"]): a for a in S["affluence_table"]}
kw = {k["keyword"]: k for k in S["keyword_table"]}
fam = {f["family"]: f for f in S["family_table"]}

# ---- deck chart data
r = df[df.rating > 0]
bands = [("Unrated", (df.rating == 0).sum()), ("1.0-1.9", ((r.rating >= 1) & (r.rating < 2)).sum()),
         ("2.0-2.9", ((r.rating >= 2) & (r.rating < 3)).sum()), ("3.0-3.9", ((r.rating >= 3) & (r.rating < 4)).sum()),
         ("4.0-4.9", ((r.rating >= 4) & (r.rating < 5)).sum()), ("Perfect 5.0", (r.rating == 5).sum())]
nr = df.number_of_reviews.dropna()
vol = [("1-10", int((nr <= 10).sum())), ("11-99", int(((nr > 10) & (nr < 100)).sum())),
       ("100-999", int(((nr >= 100) & (nr < 1000)).sum())), ("1,000+", int((nr >= 1000).sum()))]
lat = df[~df.bengali_name]
tr = lat.sort_values("number_of_reviews", ascending=False).drop_duplicates("name").head(5)
tb = lat[lat.number_of_reviews >= 500].sort_values("bayes_rating", ascending=False).drop_duplicates("name").head(5)

deck = dict(
    bands=[[a, int(b)] for a, b in bands],
    bucket=[[k, v["pct5"] * 100, v["mean_rating"], v["n"]] for k, v in bt.items()],
    volume=vol,
    aff_avail=[[k, v * 100] for k, v in S["aff_labeled_share_by_bucket"].items()],
    division=[[d["division"], d["n"], d["unrated_share"] * 100, d["mean_rating"]] for d in div],
    keywords=[[k["keyword"], k["n"]] for k in sorted(S["keyword_table"], key=lambda x: -x["n"])][:8],
    top_reviews=[[a[:30], int(b), float(c)] for a, b, c in zip(tr.name, tr.number_of_reviews, tr.rating)],
    top_adj=[[a[:30], int(b), float(c), float(d)] for a, b, c, d in zip(tb.name, tb.number_of_reviews, tb.rating, tb.bayes_rating)],
    stats=S,
)

# ---- script sections (spoken language)
sec = []
def add(title, spoken, tip=None):
    sec.append((title, spoken.strip(), tip))

add("Understanding Bangladesh's Restaurant Data (title slide)",
f"""Good morning everyone. Today I'm going to walk you through a dataset of restaurants and food places across Bangladesh. It looks simple: a name, a location, a star rating, and a review count. But it hides some surprises, and if you don't know about them, you can easily draw the wrong conclusions. By the end, you'll know what's in this data, what to trust, and what to be careful with.""",
"Pause after the last sentence. Make eye contact before moving on.")

add("The dataset at a glance",
f"""Let's start with the basics. The file we received has {n(raw)} rows and eight columns: an ID, the name, latitude and longitude, a rating, a number of reviews, something called 'affluence', and an address.

But {n(raw)} is not the real number of places. After cleaning, we have {n(uniq)} unique places. Of those, {n(S['n_rated'])} have a star rating, and together they have collected {n(S['reviews_total'])} reviews.

Geographically, almost everything is inside Bangladesh, from the far north to Cox's Bazar in the south. A small number, {S['india_rows']} places, sit just across the border in India, so we flagged those.""",
"If someone asks what 'affluence' means: there's no data dictionary. It's a number from 1 to 4 that looks like a price level.")

add("What we had to clean",
f"""Before any analysis, we had to fix four things.

First, duplicates. {p0(S['exact_dup_rows']/raw)} of the rows were exact copies of another row. One restaurant appeared {S['max_copies']} times. If we hadn't removed these, popular places would look even more popular than they are.

Second, the rating zero. {n(S['n_unrated'])} places, about {p0(S['share_unrated'])}, have a rating of zero. But zero stars isn't a real rating. Every one of those places also has no reviews. So zero here simply means 'nobody has rated this yet'. If we counted them as real zeros, the average rating would drop from {S['rating_mean']:.2f} to about 3.1, which would be completely misleading.

Third, the affluence column is {p0(1-S['share_has_aff'])} empty. And it's not empty at random. It only exists for places with at least {n(S['aff_min_reviews'])} reviews. I'll come back to that.

Fourth, not everything in the file is a restaurant. By a conservative name check, about {p0(S['non_rest_share'])} look like shops, telecom stores, schools and farms. The true number is probably higher. We flagged these rather than deleting them.""",
"The 3.1 figure is the mean rating if zeros are included: see facts/02_data_quality_issues.txt for the exact value.")

b = S["bucket_table"]
add("How good are the ratings?",
f"""Now the ratings. Among the {n(S['n_rated'])} rated places, the average is {S['rating_mean']:.2f} stars, and the median is {S['rating_median']:.1f}. People are generous: {p0(S['share_four_plus'])} of rated places score 4.0 or higher, and only {p0(S['share_below3'])} score below 3.

Look at the chart. There's a hump around 4.0, which is what you'd expect. But look at the right edge. There's a huge spike at a perfect 5.0: {n(S['n_five'])} places. That's the single most common rating in the whole dataset. Real restaurants don't behave like that, so something else is going on. Let's look at why.""")

add("The perfect 5.0 illusion",
f"""Here's the key insight of this whole analysis. Look at how the share of perfect 5.0 scores changes with the number of reviews.

Places with just one review: {p0(bt['1']['pct5'])} of them have a perfect 5.0. With two to four reviews, {p0(bt['2-4']['pct5'])}. With ten to forty-nine reviews, it drops to under {p0(bt['10-49']['pct5']+0.005)}. And with fifty or more reviews, there are zero perfect scores. Not a single one. In fact no 5.0 place has more than {int(20)} reviews.

So a 5.0 doesn't mean 'excellent'. It usually means 'one or two people liked it'. The more reviews a place has, the more its rating settles around 4. Among places with a hundred reviews or more, the highest rating anywhere is 4.7.

The practical lesson: never rank restaurants by raw rating. Either require a minimum number of reviews, or use an adjusted score that pulls small-sample ratings towards the average. We did the second, and I'll show you the results shortly.""",
"This is the most important slide. Slow down here.")

add("A few places get almost all the attention",
f"""Reviews are extremely unequal. The typical place has just {n(S['reviews_median'])} reviews. The average is {S['reviews_mean']:.0f}, which is far higher because a few giants pull it up. The biggest, Hotel Noorjahan in Cumilla, has {n(S['reviews_max'])} reviews.

{p0(S['share_reviews_le10'])} of places with reviews have ten or fewer. Only {S['n_reviews_ge1000']} places have a thousand or more. Yet the top one percent of places hold {p0(S['top1pct_share_reviews'])} of all reviews, and the top ten percent hold {p0(S['top10pct_share_reviews'])}.

What does this mean? Review count measures visibility, not quality. A place with seventeen thousand reviews and 3.5 stars is very famous, not necessarily very good. And it means only about {p0(S['reliable_share_of_all'])} of the dataset, {n(S['reliable_n'])} places, has both a rating and at least thirty reviews. That's the trustworthy core.""")

add("Affluence: handle with care",
f"""Now the mysterious affluence column. It runs from 1 to 4 and looks like a price level, but I want to stress that's our assumption, because there is no documentation.

Only {n(S['n_has_aff'])} places, {p0(S['share_has_aff'])}, have a value. Look at the chart: places with fewer than ten reviews almost never have one. Among places with a thousand or more reviews, {p0(S['aff_labeled_share_by_bucket']['1000+'])} do. So affluence exists mostly for popular places.

Among those that have it, level 2 dominates with {p0(S['aff_share_among_labeled']['2'])}, level 1 has {p0(S['aff_share_among_labeled']['1'])}, and levels 3 and 4 are rare: just {int(aff[3]['n'])} and {int(aff[4]['n'])} places. Average ratings creep up slightly with affluence, from {aff[1]['mean_rating']:.2f} at level 1 to {aff[4]['mean_rating']:.2f} at level 4, but with only {int(aff[4]['n'])} places at the top level, I wouldn't build a story on that.""")

add("Where are the places?",
f"""Now geography. The map shows the density of places. Notice how the whole country is covered, with big concentrations around Dhaka and Chattogram.

By division, Dhaka has the most, about {p0(dhaka['share'])} of the places, followed by Chattogram, Rajshahi and Khulna. One note: our geographic data uses the older seven-division map, so the newer Mymensingh division is counted inside Dhaka.

But the real story is the gap between the capital and the rest. Greater Dhaka, meaning within twenty kilometres of the centre, holds only {p0(S['greater_dhaka_share'])} of the places, yet it gets {p0(S['gd_reviews_share'])} of all the reviews. The median Dhaka place has {n(S['gd_median_reviews'])} reviews. Elsewhere it's {n(S['rest_median_reviews'])}. And {p0(S['rest_unrated_share'])} of places outside Greater Dhaka have no rating at all, compared with {p0(S['gd_unrated_share'])} inside.

Average ratings are very similar across divisions, around 4.0 to 4.2. But outside the big cities those averages rest on much thinner evidence.""",
"Point at Dhaka and Chattogram on the map when you mention them.")

add("What's in a name?",
f"""Let's peek at the names. About {p0(S['bengali_name_share'])} are written in Bengali script and the rest in English letters. That matters for two reasons. First, the same business can be spelled many ways, so matching names needs both scripts. Second, Bengali-named places tend to be less visible online: {p0(S['bengali_unrated_share'])} of them are unrated, compared with {p0(S['latin_unrated_share'])} of English-named ones, and only {p0(S['bengali_gd_share'])} are in Greater Dhaka.

Looking at keywords, 'Restaurant' appears in {n(kw['Restaurant']['n'])} names and 'Hotel' in {n(kw['Hotel (local eatery)']['n'])}. In Bangladesh, a 'hotel' is usually a local eatery, not somewhere to sleep. Then come cafes, fast food, sweets and bakeries.

We also see repeated names that suggest chains or popular naming: 'Bismillah' appears in {fam['Bismillah']['n']} names and 'Bhai Bhai' in {fam['Bhai Bhai / Vai Vai']['n']}.""")

add("Top places",
f"""Finally, who are the standouts? On the left, the most-reviewed places in the file. Hotel Noorjahan, Star Kebab and Sultan's Dine each have more than fifteen thousand reviews.

On the right, the best places once we correct for small samples, looking only at places with at least five hundred reviews. These are genuinely well-loved: high ratings backed by thousands of reviews. Notice the ratings are around 4.5, not 5.0. That's what real excellence looks like in this data.

One caveat: our charts only show English-script names, because of font limits, so some famous Bengali-named places are not shown. The full lists are in the text files.""")

add("Key takeaways",
f"""Let me close with five things to remember.

One: this file has {n(raw)} rows but only {n(uniq)} real places.
Two: a rating of zero means 'no rating', never a bad score.
Three: a perfect 5.0 almost always means one or two reviews. Don't trust it.
Four: reviews are concentrated in a few places, mainly in Dhaka, so review count measures fame, not quality.
Five: affluence is incomplete and only covers popular places.

If you remember nothing else: remove duplicates, treat zero as missing, and require a minimum number of reviews before you rank anything. Thank you. I'm happy to take questions.""")

qa = [
 ("Why not just delete the unrated places?", f"They're {p0(S['share_unrated'])} of the data and still tell us where places exist. We keep them for location and counts and exclude them from rating statistics."),
 ("How did you adjust the ratings?", f"A Bayesian average: (reviews x rating + 25 x {S['rating_global_mean_bayes']:.2f}) / (reviews + 25). With few reviews the score stays near the overall average; with many it follows the place's own rating."),
 ("Is affluence really price level?", "We don't know. It's an integer from 1 to 4 and behaves like a price level, but there's no documentation. Confirm with the data owner."),
 ("How accurate is the division information?", "It comes from matching each coordinate to the nearest known populated place, so border areas can be off. Mymensingh is merged into Dhaka."),
 ("Can we trust the ratings of unknown places?", f"Only with caution. Just {p0(S['reliable_share_of_all'])} of places have a rating with 30+ reviews."),
]

md = ["# Presentation Script: Bangladesh Restaurant Data", "",
      f"**Estimated speaking time:** about {int(sum(len(s[1].split()) for s in sec)/140)+1} minutes at a comfortable pace (140 words per minute).",
      "**How to use this:** each section matches one slide in `restaurants_presentation.pptx` (the same text is in the slide's speaker notes). Italic lines are delivery tips, not words to read aloud.", "", "---", ""]
for i, (t, sp, tip) in enumerate(sec, 1):
    md += [f"## Slide {i}: {t}", "", sp, ""]
    if tip:
        md += [f"*Tip: {tip}*", ""]
    md += ["---", ""]
md += ["## Likely questions and short answers", ""]
for q, a in qa:
    md += [f"**Q: {q}**  ", f"A: {a}", ""]
md += ["---", "", "## Quick glossary", "",
       "- **Unrated:** a place with rating 0 and no reviews. Means 'no data', not 'bad'.",
       "- **Median:** the middle value. Half of places are above it, half below.",
       "- **Adjusted (Bayesian) rating:** a rating corrected for how many reviews back it.",
       "- **Affluence:** an integer 1-4, probably a price level (not documented).",
       "- **Greater Dhaka:** any place within 20 km of the city centre.", ""]
open(os.path.join(OUT, "presentation_script.md"), "w", encoding="utf-8").write("\n".join(md))
deck["stats"] = {k: v for k, v in S.items() if k not in ("top_reviews", "top_bayes")}
deck["notes"] = [s[1] for s in sec]
json.dump(deck, open(os.path.join(OUT, "deck_data.json"), "w", encoding="utf-8"), ensure_ascii=False, default=float)
print("words:", sum(len(s[1].split()) for s in sec), "slides:", len(sec))
