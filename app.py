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

    show_group_relationships(products, category)
    show_price_relationship(products)
    show_rating_relationship(products)

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
    ["After cleaning", "Before cleaning", "Cleaning impact"],
    horizontal=True,
)

if view == "Cleaning impact":
    show_cleaning_impact(before, after)
elif view == "Before cleaning":
    show_catalog(before, category, budget)
else:
    show_catalog(after, category, budget, cleaned=True)

