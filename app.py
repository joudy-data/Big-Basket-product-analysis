from pathlib import Path

import pandas as pd
import streamlit as st


st.set_page_config(page_title="BigBasket Product Catalog", layout="wide")

FOLDER = Path(__file__).resolve().parent
GREEN = "#5B8C25"
RED = "#DE4739"

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
        "Check": ["Missing product names", "Missing brands",
                  "Missing descriptions", "Missing ratings"],
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
        product_type = row.get("type", "Product")
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

    st.subheader("Listings and discounts by category")
    counts = products.groupby("category").size()
    discount_counts = products.loc[discounted].groupby("category").size()
    chart = pd.DataFrame({
        "All listings": counts,
        "Discounted listings": discount_counts.reindex(counts.index, fill_value=0),
    }).sort_values("All listings", ascending=False)

    st.bar_chart(chart, color=[GREEN, RED], stack=False)

    st.subheader("Product listings")
    table = products[list(COLUMNS)].rename(columns=COLUMNS).copy()

    if cleaned:
        # Add friendly labels to the display table after calculating the metrics.
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
    ["Cleaning impact", "Before cleaning", "After cleaning"],
    horizontal=True,
)

if view == "Cleaning impact":
    show_cleaning_impact(before, after)
elif view == "Before cleaning":
    show_catalog(before, category, budget)
else:
    show_catalog(after, category, budget, cleaned=True)
