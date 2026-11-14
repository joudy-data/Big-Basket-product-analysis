from pathlib import Path

import pandas as pd
import streamlit as st

st.set_page_config(page_title="BigBasket Dashboard", layout="wide")

GREEN = "#78A927"
RED = "#DE4739"
YELLOW = "#FFE36E"
CREAM = "#FFF9E8"

folder = Path(__file__).resolve().parent
raw_file = folder / "BigBasket Products.csv"
clean_file = folder / "BigBasket_Cleaned.csv"


def load_catalog(file):
    catalog = pd.read_csv(file)
    catalog = catalog.rename(columns={"product": "product_name"})

    # Convert text prices such as "₹1,200" to numbers before filtering.
    for column in ["sale_price", "market_price", "rating"]:
        text = catalog[column].astype("string").str.strip()
        text = text.str.replace("₹", "", regex=False)
        text = text.str.replace(",", "", regex=False)
        catalog[column] = pd.to_numeric(text, errors="coerce")

    return catalog


st.markdown(
    f"""
    <style>
    .stApp {{ background: {CREAM}; }}
    [data-testid="stSidebar"] {{ background: #ECF6C9; }}
    [data-testid="stMetric"] {{
        background: white;
        color: #20351B;
        border-top: 5px solid {GREEN};
        border-radius: 12px;
        padding: 14px;
    }}
    .basket-banner {{
        background: {YELLOW};
        border-left: 10px solid {RED};
        border-radius: 16px;
        padding: 20px 24px;
        margin-bottom: 16px;
    }}
    .basket-banner h1, .basket-banner p {{
        color: #20351B;
        margin: 0;
        padding: 0;
    }}
    </style>

    <div class="basket-banner">
        <h1>BigBasket Product Catalog</h1>
        <p>Compare prices, discounts, and ratings across supermarket categories.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

for file in [raw_file, clean_file]:
    if not file.exists():
        st.error(f"Place {file.name} in the same folder as app.py.")
        st.stop()

before = load_catalog(raw_file)
after = load_catalog(clean_file)

st.sidebar.header("Catalog filters")
categories = sorted(before["category"].dropna().unique())
category = st.sidebar.selectbox("Category", ["All categories", *categories])

use_budget = st.sidebar.checkbox("Set a maximum price")
budget = st.sidebar.number_input(
    "Maximum sale price (₹)",
    min_value=0.0,
    value=500.0,
    step=10.0,
    disabled=not use_budget,
)

view = st.radio(
    "Dashboard view",
    ["Before cleaning", "After cleaning", "Cleaning impact"],
    horizontal=True,
)

if view == "Cleaning impact":
    st.subheader("What changed across the full catalog?")
    st.caption("These counts cover the full dataset, regardless of the sidebar filters.")

    left, middle, right = st.columns(3)
    left.metric("Before cleaning", f"{len(before):,}")
    middle.metric("After cleaning", f"{len(after):,}")
    right.metric("Listings removed", f"{len(before) - len(after):,}")

    fields = ["product_name", "brand", "description", "rating"]
    missing = pd.DataFrame({
        "Before": before[fields].isna().sum(),
        "After": after[fields].isna().sum(),
    })
    missing.index = ["Product name", "Brand", "Description", "Rating"]

    st.bar_chart(missing, color=[RED, GREEN])
    st.dataframe(missing)
    st.caption(
        "The cleaning step removes listings with no product name and labels missing "
        "brands and descriptions. Missing ratings stay blank."
    )
    st.stop()

catalog = before if view == "Before cleaning" else after

if category != "All categories":
    catalog = catalog[catalog["category"] == category]

if use_budget:
    catalog = catalog[catalog["sale_price"] <= budget]

if catalog.empty:
    st.info("No listings match your filters. Try a higher budget or another category.")
    st.stop()

products = catalog.copy()
market_price = products["market_price"].where(products["market_price"] > 0)
products["Discount (%)"] = (
    (market_price - products["sale_price"]) / market_price * 100
).round(1)

discounted = products["sale_price"] < market_price
rated = products["rating"].count()
median_price = products["sale_price"].median()
average_rating = products["rating"].mean()

a, b, c, d = st.columns(4)
a.metric("Listings", f"{len(products):,}")
b.metric("Median sale price", f"₹{median_price:,.2f}" if pd.notna(median_price) else "—")
c.metric("Discounted listings", f"{discounted.sum():,}")
d.metric("Average rating", f"{average_rating:.2f} / 5" if rated else "—")
st.caption(f"Average rating uses {rated:,} of {len(products):,} listings.")

st.subheader("Listings and discounts by category")
chart = products.groupby("category").size().rename("All listings").to_frame()
chart["Discounted listings"] = (
    products.loc[discounted].groupby("category").size()
    .reindex(chart.index, fill_value=0)
)
st.bar_chart(chart, color=[GREEN, RED])

st.subheader("Product listings")
columns = [
    "product_name", "brand", "category",
    "sale_price", "market_price", "Discount (%)", "rating",
]
table = products[columns].rename(columns={
    "product_name": "Product",
    "brand": "Brand",
    "category": "Category",
    "sale_price": "Sale price (₹)",
    "market_price": "Market price (₹)",
    "rating": "Rating",
})
st.dataframe(table, hide_index=True)
