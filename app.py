from pathlib import Path

import pandas as pd
import streamlit as st


st.set_page_config(page_title="BigBasket Dashboard", layout="wide")

GREEN = "#78A927"
RED = "#DE4739"
YELLOW = "#FFE36E"
CREAM = "#FFF9E8"

folder = Path(__file__).resolve().parent


def load_catalog(filename):
    path = folder / filename

    if not path.is_file():
        st.error(f"Place {filename} in the same folder as app.py.")
        st.stop()

    catalog = pd.read_csv(path)
    catalog = catalog.rename(columns={"product": "product_name"})

    # Convert text prices such as ₹1,200 before applying the budget filter.
    for column in ["sale_price", "market_price", "rating"]:
        values = catalog[column].astype("string").str.strip()
        values = values.str.replace("₹", "", regex=False)
        values = values.str.replace(",", "", regex=False)
        catalog[column] = pd.to_numeric(values, errors="coerce")

    return catalog


def show_cleaning_impact(before, after):
    st.subheader("What changed after cleaning?")
    st.caption("This comparison covers the full catalog.")

    removed = before.loc[~before["index"].isin(after["index"])]
    left, middle, right = st.columns(3)
    left.metric("Before cleaning", f"{len(before):,}")
    middle.metric("After cleaning", f"{len(after):,}")
    right.metric("Listings removed", f"{len(removed):,}")

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
            "Remove the listing with no product name",
            "Fill with Unknown",
            "Fill with Not Available",
            "Keep blank and exclude from the average rating",
        ],
    })
    st.dataframe(summary, hide_index=True)

    # Match the same listing across both files using its original ID.
    matched = before.merge(after, on="index", suffixes=("_before", "_after"))
    examples = []

    for field, label in [("brand", "Brand"), ("description", "Description")]:
        old = f"{field}_before"
        new = f"{field}_after"
        filled = matched.loc[matched[old].isna() & matched[new].notna()]

        if not filled.empty:
            row = filled.iloc[0]
            examples.append({
                "Listing": row["product_name_after"],
                "Field": label,
                "Before": "Blank",
                "After": row[new],
            })

    if not removed.empty:
        row = removed.iloc[0]
        examples.append({
            "Listing": f"{row['category']} · {row['type']}",
            "Field": "Product name",
            "Before": "Blank" if pd.isna(row["product_name"]) else row["product_name"],
            "After": "Listing removed",
        })

    if examples:
        st.subheader("Examples from the data")
        st.dataframe(pd.DataFrame(examples), hide_index=True)


def show_catalog(catalog, category, use_budget, budget):
    if category != "All categories":
        catalog = catalog.loc[catalog["category"] == category]

    if use_budget:
        catalog = catalog.loc[catalog["sale_price"] <= budget]

    if catalog.empty:
        st.info("No listings match these filters. Try a higher budget or another category.")
        return

    products = catalog.copy()
    market_price = products["market_price"].where(products["market_price"] > 0)
    products["discount_pct"] = (
        (market_price - products["sale_price"]) / market_price * 100
    ).round(1)

    discounted = products["sale_price"] < market_price
    median_price = products["sale_price"].median()
    rated = products["rating"].count()
    average_rating = products["rating"].mean()

    count_card, price_card, discount_card, rating_card = st.columns(4)
    count_card.metric("Listings", f"{len(products):,}")
    price_card.metric(
        "Median sale price",
        f"₹{median_price:,.2f}" if pd.notna(median_price) else "—",
    )
    discount_card.metric("Discounted listings", f"{discounted.sum():,}")
    rating_card.metric("Average rating", f"{average_rating:.2f} / 5" if rated else "—")
    st.caption(f"Average rating uses {rated:,} of {len(products):,} listings.")

    st.subheader("Listings and discounts by category")
    chart = products.groupby("category").size().rename("All listings").to_frame()
    chart["Discounted listings"] = (
        products.loc[discounted]
        .groupby("category")
        .size()
        .reindex(chart.index, fill_value=0)
    )
    st.bar_chart(chart, color=[GREEN, RED], stack=False)

    st.subheader("Product listings")
    columns = {
        "product_name": "Product",
        "category": "Category",
        "brand": "Brand",
        "sale_price": "Sale price (₹)",
        "market_price": "Market price (₹)",
        "discount_pct": "Discount (%)",
        "rating": "Rating",
    }
    st.dataframe(products[list(columns)].rename(columns=columns), hide_index=True)


st.markdown(
    f"""
    <style>
        .stApp {{ background-color: {CREAM}; }}
        [data-testid="stSidebar"] {{ background-color: #ECF6C9; }}
        [data-testid="stMetric"] {{
            background-color: #FFFFFF;
            color: #20351B;
            border-top: 5px solid {GREEN};
            border-radius: 12px;
            padding: 14px;
        }}
        .basket-banner {{
            background-color: {YELLOW};
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
        <p>Explore prices, discounts, and ratings before and after cleaning.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

before = load_catalog("BigBasket Products.csv")
after = load_catalog("BigBasket_Cleaned.csv")

st.sidebar.header("Catalog filters")
st.sidebar.caption(
    "BigBasket product catalog from Kaggle. Each row represents a product "
    "listing. Prices are in Indian rupees (₹)."
)

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

impact_tab, before_tab, after_tab = st.tabs([
    "Cleaning impact",
    "Before cleaning",
    "After cleaning",
])

with impact_tab:
    show_cleaning_impact(before, after)

with before_tab:
    show_catalog(before, category, use_budget, budget)

with after_tab:
    show_catalog(after, category, use_budget, budget)
