from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st


st.set_page_config(page_title="BigBasket Product Catalog", layout="wide")

FOLDER = Path(__file__).resolve().parent
GREEN = "#5B8C25"
RED = "#DE4739"
PRICE_BANDS = ["Under ₹100", "₹100–<250", "₹250–<500", "₹500–<1,000", "₹1,000+"]

KAGGLE_URL = (
    "https://www.kaggle.com/datasets/"
    "surajjha101/bigbasket-entire-product-list-28k-datapoints"
)

COLUMNS = {
    "product_name": "Product",
    "category": "Category",
    "brand": "Brand",
    "description": "Description",
    "sale_price": "Sale price (₹)",
    "market_price": "Market price (₹)",
    "discount_pct": "Discount (%)",
    "rating": "Rating",
}


@st.cache_data
def load_catalog(filename):
    path = FOLDER / filename

    if not path.is_file():
        st.error(f"Add {filename} beside app.py in your GitHub repository.")
        st.stop()

    catalog = pd.read_csv(path)
    catalog = catalog.rename(columns={"product": "product_name"})

    required = {
        "index", "product_name", "category", "brand", "description",
        "sale_price", "market_price", "rating",
    }
    missing = required.difference(catalog.columns)

    if missing:
        st.error(f"{filename} is missing columns: {', '.join(sorted(missing))}")
        st.stop()

    # Keep prices and ratings numeric in both versions.
    for column in ["sale_price", "market_price", "rating"]:
        values = catalog[column].astype("string").str.strip()
        values = values.str.replace("₹", "", regex=False)
        values = values.str.replace(",", "", regex=False)
        catalog[column] = pd.to_numeric(values, errors="coerce")

    return catalog


def show_cleaning_impact(before, after):
    st.subheader("Cleaning impact")
    st.caption("Full-catalog comparison. Category and budget filters apply to the catalog views.")

    removed = before.loc[~before["index"].isin(after["index"])]
    first, second, third = st.columns(3)
    first.metric("Original listings", f"{len(before):,}")
    second.metric("Cleaned listings", f"{len(after):,}")
    third.metric("Listings removed", f"{len(removed):,}")

    fields = ["product_name", "brand", "description", "rating"]
    summary = pd.DataFrame({
        "Check": [
            "Missing product names",
            "Missing brands",
            "Missing descriptions",
            "Missing ratings",
        ],
        "Before": before[fields].isna().sum().tolist(),
        "After": after[fields].isna().sum().tolist(),
        "Cleaning decision": [
            "Remove listings without a product name",
            "Fill blank brands with Unknown",
            "Fill blank descriptions with Not Available",
            "Keep missing ratings blank for calculations",
        ],
    })
    st.dataframe(summary, hide_index=True)

    st.subheader("Inspect a cleaning change")
    change = st.selectbox(
        "Choose an example",
        ["Missing description", "Missing brand", "Removed listing"],
    )

    if change == "Removed listing":
        if removed.empty:
            st.info("No removed listings were found in these files.")
            return

        row = removed.iloc[0]
        product_type = row.get("product_type", row.get("type", "Product"))
        st.write(f"**Listing #{row['index']}** · {row['category']} · {product_type}")
        left, right = st.columns(2)
        left.markdown("**Before cleaning**")
        left.write("Product name: blank" if pd.isna(row["product_name"]) else row["product_name"])
        right.markdown("**After cleaning**")
        right.write("Listing removed")
        return

    field = "description" if change == "Missing description" else "brand"

    # Match the same product across both CSVs using its original listing ID.
    blanks = before.loc[before[field].isna(), ["index", "product_name"]]
    filled = blanks.merge(after[["index", field]].dropna(subset=[field]), on="index")

    if filled.empty:
        st.info(f"No filled {field} values were found in these files.")
        return

    row = filled.iloc[0]
    st.write(f"**{row['product_name']}** · Listing #{row['index']}")
    left, right = st.columns(2)
    left.markdown("**Before cleaning**")
    left.write("Blank")
    right.markdown("**After cleaning**")
    right.write(row[field])


def show_price_relationship(products):
    st.subheader("Market price vs. sale price")
    valid = products.loc[
        products["sale_price"].gt(0) & products["market_price"].gt(0),
        ["product_name", "category", "market_price", "sale_price", "discount_pct"],
    ].copy()

    if valid.empty:
        st.info("No listings have two positive prices in this selection.")
        return

    points = valid.sample(n=min(2500, len(valid)), random_state=42).fillna(
        {"product_name": "Unknown", "category": "Unknown"}
    )
    points["Price comparison"] = "At market price"
    points.loc[
        points["sale_price"].lt(points["market_price"]), "Price comparison"
    ] = "Below market price"
    points.loc[
        points["sale_price"].gt(points["market_price"]), "Price comparison"
    ] = "Above market price"

    minimum = float(valid[["market_price", "sale_price"]].min().min())
    maximum = float(valid[["market_price", "sale_price"]].max().max())
    domain = [minimum / 1.1, maximum * 1.1]
    x = alt.X(
        "market_price:Q",
        title="Market price (₹, log scale)",
        scale=alt.Scale(type="log", domain=domain),
    )
    y = alt.Y(
        "sale_price:Q",
        title="Sale price (₹, log scale)",
        scale=alt.Scale(type="log", domain=domain),
    )
    diagonal = alt.Chart(
        pd.DataFrame({"market_price": domain, "sale_price": domain})
    ).mark_line(color="#5E6359", strokeDash=[5, 4]).encode(x=x, y=y)

    scatter = alt.Chart(points).mark_circle(size=42, opacity=0.42).encode(
        x=x,
        y=y,
        color=alt.Color(
            "Price comparison:N",
            scale=alt.Scale(
                domain=["Below market price", "At market price", "Above market price"],
                range=[GREEN, "#777D71", RED],
            ),
            legend=alt.Legend(title=None, orient="bottom"),
        ),
        tooltip=[
            alt.Tooltip("product_name:N", title="Product"),
            alt.Tooltip("category:N", title="Category"),
            alt.Tooltip("market_price:Q", title="Market price (₹)", format=",.2f"),
            alt.Tooltip("sale_price:Q", title="Sale price (₹)", format=",.2f"),
            alt.Tooltip("discount_pct:Q", title="Discount (%)", format=".1f"),
        ],
    )
    st.altair_chart((diagonal + scatter).properties(height=360), width="stretch")
    st.caption(
        f"Showing {len(points):,} of {len(valid):,} listings with two positive prices. "
        "The dashed line marks equal prices. Points below it are discounted."
    )


def show_group_relationships(products, category):
    st.subheader("Pricing and discounts by product group")
    group = "category"
    if category != "All categories" and "sub_category" in products:
        group = "sub_category"
    group_label = "Subcategory" if group == "sub_category" else "Category"

    valid = products.loc[
        products["sale_price"].ge(0), [group, "sale_price", "market_price"]
    ].copy()
    valid[group] = valid[group].fillna("Unknown")

    if valid.empty:
        st.info("No listings have a usable sale price in this selection.")
        return

    valid["comparable"] = valid["market_price"].gt(0)
    valid["discounted"] = valid["comparable"] & valid["sale_price"].lt(valid["market_price"])
    summary = valid.groupby(group, as_index=False).agg(
        median_price=("sale_price", "median"),
        listings=("sale_price", "size"),
        comparable=("comparable", "sum"),
        discounted=("discounted", "sum"),
    )
    summary["discount_share"] = summary["discounted"].div(
        summary["comparable"].where(summary["comparable"].gt(0))
    )
    shown = summary.nlargest(12, "listings")
    order = shown.sort_values("median_price", ascending=False)[group].tolist()

    base = alt.Chart(shown).encode(y=alt.Y(f"{group}:N", sort=order, title=group_label))
    left, right = st.columns(2)

    with left:
        st.altair_chart(
            base.mark_bar(color=GREEN).encode(
                x=alt.X("median_price:Q", title="Median sale price (₹)"),
                tooltip=[
                    alt.Tooltip(f"{group}:N", title=group_label),
                    alt.Tooltip("median_price:Q", title="Median sale price (₹)", format=",.2f"),
                    alt.Tooltip("listings:Q", title="Listings with sale price", format=","),
                ],
            ).properties(height=330),
            width="stretch",
        )

    with right:
        st.altair_chart(
            base.mark_bar(color=RED).encode(
                x=alt.X(
                    "discount_share:Q",
                    title="Share of listings discounted",
                    axis=alt.Axis(format="%"),
                    scale=alt.Scale(domain=[0, 1]),
                ),
                tooltip=[
                    alt.Tooltip(f"{group}:N", title=group_label),
                    alt.Tooltip("discount_share:Q", title="Discounted share", format=".1%"),
                    alt.Tooltip("discounted:Q", title="Discounted listings", format=","),
                    alt.Tooltip("comparable:Q", title="Listings with comparable prices", format=","),
                ],
            ).properties(height=330),
            width="stretch",
        )

    st.caption(
        f"Showing {len(shown)} of {len(summary)} {group_label.lower()} groups ranked by listing count. "
        "Discount share uses listings with a valid sale price and a positive market price."
    )


def show_rating_relationship(products):
    st.subheader("Sale price vs. customer rating")
    eligible = products.loc[products["sale_price"].ge(0), ["sale_price", "rating"]].copy()

    if eligible.empty or eligible["rating"].count() == 0:
        st.info("No recorded ratings with a valid sale price in this selection.")
        return

    eligible["price_band"] = pd.cut(
        eligible["sale_price"],
        bins=[0, 100, 250, 500, 1000, float("inf")],
        labels=PRICE_BANDS,
        right=False,
    )
    summary = eligible.groupby("price_band", observed=True, as_index=False).agg(
        mean_rating=("rating", "mean"),
        rated=("rating", "count"),
        listings=("rating", "size"),
    )
    summary["coverage"] = summary["rated"] / summary["listings"]

    chart = alt.Chart(summary).mark_circle(color=GREEN, opacity=0.85).encode(
        x=alt.X(
            "price_band:N",
            sort=PRICE_BANDS,
            title="Sale-price band",
            axis=alt.Axis(labelAngle=0),
        ),
        y=alt.Y(
            "mean_rating:Q",
            title="Average rating out of 5",
            scale=alt.Scale(domain=[0, 5]),
        ),
        size=alt.Size("rated:Q", title="Rated listings", scale=alt.Scale(range=[60, 650])),
        tooltip=[
            alt.Tooltip("price_band:N", title="Price band"),
            alt.Tooltip("mean_rating:Q", title="Average rating", format=".2f"),
            alt.Tooltip("rated:Q", title="Rated listings", format=","),
            alt.Tooltip("listings:Q", title="All listings", format=","),
            alt.Tooltip("coverage:Q", title="Rating coverage", format=".1%"),
        ],
    )
    st.altair_chart(chart.properties(height=300), width="stretch")
    st.caption(
        f"{eligible['rating'].count():,} of {len(eligible):,} listings with valid sale prices have a rating. "
        "Larger dots represent more rated listings. Bands without ratings have no dot."
    )


def show_catalog(catalog, category, budget, cleaned=False):
    if category != "All categories":
        catalog = catalog.loc[catalog["category"].eq(category)]

    if budget is not None:
        catalog = catalog.loc[catalog["sale_price"].le(budget)]

    if catalog.empty:
        st.info("No listings match these filters. Try a higher budget or a different category.")
        return

    products = catalog.copy()
    market_price = products["market_price"].where(products["market_price"].gt(0))
    discounted = products["sale_price"].lt(market_price)
    products["discount_pct"] = (
        (market_price - products["sale_price"]) / market_price * 100
    ).round(1)

    median_price = products["sale_price"].median()
    mean_rating = products["rating"].mean()
    rated_count = products["rating"].count()

    first, second, third, fourth = st.columns(4)
    first.metric("Listings", f"{len(products):,}")
    second.metric("Median sale price", f"₹{median_price:,.2f}" if pd.notna(median_price) else "—")
    third.metric("Discounted listings", f"{discounted.sum():,}")
    fourth.metric("Average rating", f"{mean_rating:.2f} / 5" if rated_count else "—")
    st.caption(f"The average uses {rated_count:,} recorded ratings out of {len(products):,} listings.")

    show_price_relationship(products)
    show_group_relationships(products, category)
    show_rating_relationship(products)

    st.subheader("Product listings")
    table = products[list(COLUMNS)].rename(columns=COLUMNS).copy()

    if cleaned:
        # Add display labels after calculating the metrics.
        table["Rating"] = table["Rating"].map(
            lambda value: "Not rated" if pd.isna(value) else f"{value:.1f}"
        )

    st.dataframe(
        table,
        hide_index=True,
        column_config={
            "Description": st.column_config.TextColumn("Description", width="medium"),
            "Sale price (₹)": st.column_config.NumberColumn(format="%.2f"),
            "Market price (₹)": st.column_config.NumberColumn(format="%.2f"),
            "Discount (%)": st.column_config.NumberColumn(format="%.1f"),
        },
    )


st.markdown(
    """
    <style>
    .stApp { background-color: #FFF9E8; }
    [data-testid="stSidebar"] { background-color: #ECF6C9; }
    [data-testid="stMetric"] {
        background-color: #FFFFFF;
        border-top: 5px solid #78A927;
        border-radius: 12px;
        padding: 14px;
    }
    [data-testid="stMetric"] * { color: #20351B; }
    .basket-banner {
        background-color: #FFE36E;
        border-left: 10px solid #DE4739;
        border-radius: 16px;
        padding: 20px 24px;
    }
    .basket-banner h1, .basket-banner p {
        color: #20351B;
        margin: 0;
        padding: 0;
    }
    </style>
    <div class="basket-banner">
        <h1>BigBasket Product Catalog</h1>
        <p>Explore prices, discounts, and ratings before and after cleaning.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

before = load_catalog("BigBasket Products.csv")
after = load_catalog("BigBasket_Cleaned.csv")

st.sidebar.header("Catalog filters")
st.sidebar.caption(
    "Each row represents a BigBasket product listing. "
    "Prices are in Indian rupees (₹)."
)
st.sidebar.markdown(f"[View the Kaggle dataset]({KAGGLE_URL})")

categories = sorted(before["category"].dropna().unique())
category = st.sidebar.selectbox("Category", ["All categories", *categories])

use_budget = st.sidebar.checkbox("Set a maximum sale price")
price_limit = st.sidebar.number_input(
    "Maximum sale price (₹)",
    min_value=0.0,
    value=500.0,
    step=10.0,
    disabled=not use_budget,
)
budget = price_limit if use_budget else None

view = st.radio(
    "Dashboard view",
    ["After cleaning", "Before cleaning", "Cleaning impact"],
    horizontal=True,
)

if view == "Cleaning impact":
    show_cleaning_impact(before, after)
elif view == "Before cleaning":
    show_catalog(before, category, budget)
else:
    show_catalog(after, category, budget, cleaned=True)
