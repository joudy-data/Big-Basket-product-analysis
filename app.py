from html import escape
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st


st.set_page_config(page_title="BigBasket Product Catalog", layout="wide")

ROOT = Path(__file__).resolve().parent
GREEN = "#5B8C25"
RED = "#C84937"
KAGGLE_URL = (
    "https://www.kaggle.com/datasets/"
    "surajjha101/bigbasket-entire-product-list-28k-datapoints"
)
ALL_CATEGORIES = "All categories"
PRICE_BANDS = ["Under ₹100", "₹100–<250", "₹250–<500", "₹500–<1,000", "₹1,000+"]
TABLE_COLUMNS = {
    "product_name": "Product",
    "category": "Category",
    "brand": "Brand",
    "description": "Description",
    "sale_price": "Sale price (₹)",
    "market_price": "Market price (₹)",
    "discount_pct": "Discount (%)",
    "rating": "Rating",
}

PAGE_HEADER = """
<style>
    .bb-banner {
        padding: 1.1rem 1.4rem;
        border: 1px solid #e2eacd;
        border-left: 6px solid #5b8c25;
        border-radius: 14px;
        background: #f2f7e7;
        color: #22351b;
    }
    .bb-banner h1 {
        padding: 0;
        margin: 0;
        font-size: clamp(1.6rem, 4vw, 2.4rem);
        color: #22351b;
    }
    .bb-banner p { margin: .35rem 0 0; }
    .bb-comparison {
        width: 100%;
        table-layout: fixed;
        border-collapse: separate;
        border-spacing: 0;
        border: 1px solid #e2e8d8;
        border-radius: 12px;
        overflow: hidden;
        background: #ffffff;
        color: #22351b;
    }
    .bb-comparison th, .bb-comparison td {
        padding: .65rem clamp(.35rem, 1.5vw, 1rem);
        border: 0;
        border-bottom: 1px solid #eaf0e1;
        text-align: left;
        vertical-align: middle;
        overflow-wrap: anywhere;
        font-size: clamp(.78rem, 1.2vw, .95rem);
    }
    .bb-comparison thead th { background: #edf4e0; }
    .bb-comparison tbody th { font-weight: 600; }
    .bb-comparison tbody tr:nth-child(even) { background: #f8faf4; }
    .bb-comparison tbody tr:last-child > * { border-bottom: 0; }
    .bb-value { font-variant-numeric: tabular-nums; }
    .bb-track {
        height: 6px;
        margin-top: 5px;
        border-radius: 6px;
        background: #eaf0e4;
    }
    .bb-track span { display: block; height: 100%; border-radius: inherit; }
    .bb-price { background: #5b8c25; }
    .bb-discount { background: #c84937; }
</style>
<div class="bb-banner">
    <h1>BigBasket Product Catalog</h1>
    <p>Compare product prices, discounts, and customer ratings.</p>
</div>
"""


@st.cache_data
def load_catalog(filename):
    path = ROOT / filename
    if not path.is_file():
        st.error(f"Missing file: {filename}. Place it beside app.py.")
        st.stop()

    data = pd.read_csv(path).rename(columns={"product": "product_name"})
    required = {
        "index", "product_name", "category", "brand", "description",
        "sale_price", "market_price", "rating",
    }
    missing = required.difference(data.columns)
    if missing:
        st.error(f"{filename} is missing these columns: {', '.join(sorted(missing))}.")
        st.stop()

    for column in ("sale_price", "market_price", "rating"):
        values = data[column].astype("string").str.strip()
        values = values.str.replace("₹", "", regex=False).str.replace(",", "", regex=False)
        data[column] = pd.to_numeric(values, errors="coerce").replace(
            [float("inf"), float("-inf")], float("nan")
        )

    return data


def show_group_comparison(products, selected_category):
    group = "category"
    if selected_category != ALL_CATEGORIES and "sub_category" in products.columns:
        group = "sub_category"

    label = "Subcategory" if group == "sub_category" else "Category"
    st.subheader(f"Prices & discounts by {label.lower()}")

    valid = products.loc[
        products["sale_price"].ge(0), [group, "sale_price", "market_price"]
    ].copy()
    if valid.empty:
        st.info("No listings with a valid sale price match your filters.")
        return

    valid[group] = valid[group].fillna("Unknown")
    valid["comparable"] = valid["market_price"].gt(0)
    valid["discounted"] = (
        valid["comparable"] & valid["sale_price"].lt(valid["market_price"])
    )
    summary = valid.groupby(group, as_index=False).agg(
        median_price=("sale_price", "median"),
        comparable=("comparable", "sum"),
        discounted=("discounted", "sum"),
    ).sort_values(["median_price", group], ascending=[False, True])

    max_price = max(summary["median_price"].max(), 1)
    rows = []
    for name, price, comparable, discounted in summary.itertuples(index=False, name=None):
        price_width = 100 * price / max_price
        rate = 100 * discounted / comparable if comparable else 0
        rate_text = f"{rate:.1f}%" if comparable else "—"
        details = f"{discounted:,} discounted / {comparable:,} comparable listings"

        rows.append(f"""
            <tr>
                <th scope="row">{escape(str(name))}</th>
                <td>
                    <strong class="bb-value">₹{price:,.2f}</strong>
                    <div class="bb-track" aria-hidden="true">
                        <span class="bb-price" style="width:{price_width:.2f}%"></span>
                    </div>
                </td>
                <td title="{details}">
                    <strong class="bb-value">{rate_text}</strong>
                    <div class="bb-track" aria-hidden="true">
                        <span class="bb-discount" style="width:{rate:.2f}%"></span>
                    </div>
                </td>
            </tr>
        """)

    st.html(f"""
        <table class="bb-comparison" aria-label="Prices and discounts by {label.lower()}">
            <colgroup>
                <col style="width:44%">
                <col style="width:28%">
                <col style="width:28%">
            </colgroup>
            <thead>
                <tr>
                    <th scope="col">{label}</th>
                    <th scope="col">Median price</th>
                    <th scope="col">Discounted</th>
                </tr>
            </thead>
            <tbody>{"".join(rows)}</tbody>
        </table>
    """)
    st.caption("Discount rates use listings with a valid sale price and a positive market price.")


def show_price_chart(products):
    st.subheader("Market price vs. sale price")
    valid = products.loc[
        products["sale_price"].gt(0) & products["market_price"].gt(0),
        ["product_name", "category", "market_price", "sale_price", "discount_pct"],
    ]
    if valid.empty:
        st.info("No listings with two positive prices match your filters.")
        return

    points = valid.sample(n=min(len(valid), 2500), random_state=42).fillna(
        {"product_name": "Unknown", "category": "Unknown"}
    )
    points["comparison"] = "At market price"
    points.loc[points["sale_price"].lt(points["market_price"]), "comparison"] = "Below market price"
    points.loc[points["sale_price"].gt(points["market_price"]), "comparison"] = "Above market price"

    prices = valid[["market_price", "sale_price"]]
    domain = [float(prices.min().min()) / 1.1, float(prices.max().max()) * 1.1]
    scale = alt.Scale(type="log", domain=domain)
    x = alt.X("market_price:Q", title="Market price (₹, log scale)", scale=scale)
    y = alt.Y("sale_price:Q", title="Sale price (₹, log scale)", scale=scale)

    diagonal = alt.Chart(
        pd.DataFrame({"market_price": domain, "sale_price": domain})
    ).mark_line(color="#778071", strokeDash=[5, 4]).encode(x=x, y=y)

    scatter = alt.Chart(points).mark_circle(size=42, opacity=0.45).encode(
        x=x,
        y=y,
        color=alt.Color(
            "comparison:N",
            scale=alt.Scale(
                domain=["Below market price", "At market price", "Above market price"],
                range=[GREEN, "#778071", RED],
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

    st.altair_chart((diagonal + scatter).properties(height=350), width="stretch")
    st.caption(
        f"{len(points):,} of {len(valid):,} eligible listings shown. "
        "Points below the dashed line are discounted."
    )


def show_rating_chart(products):
    st.subheader("Average rating by price band")
    eligible = products.loc[
        products["sale_price"].ge(0), ["sale_price", "rating"]
    ].copy()
    rated_count = eligible["rating"].count()
    if not rated_count:
        st.info("No rated listings with a valid sale price match your filters.")
        return

    eligible["price_band"] = pd.cut(
        eligible["sale_price"],
        bins=[0, 100, 250, 500, 1000, float("inf")],
        labels=PRICE_BANDS,
        right=False,
    )
    summary = eligible.groupby("price_band", observed=True, as_index=False).agg(
        average_rating=("rating", "mean"),
        rated=("rating", "count"),
        listings=("rating", "size"),
    )
    summary["coverage"] = summary["rated"] / summary["listings"]

    chart = alt.Chart(summary).mark_circle(color=GREEN, opacity=0.85).encode(
        x=alt.X(
            "price_band:N",
            sort=PRICE_BANDS,
            title="Sale-price band",
            axis=alt.Axis(labelAngle=-20),
        ),
        y=alt.Y(
            "average_rating:Q",
            title="Average rating out of 5",
            scale=alt.Scale(domain=[0, 5]),
        ),
        size=alt.Size("rated:Q", title="Rated listings", scale=alt.Scale(range=[60, 650])),
        tooltip=[
            alt.Tooltip("price_band:N", title="Price band"),
            alt.Tooltip("average_rating:Q", title="Average rating", format=".2f"),
            alt.Tooltip("rated:Q", title="Rated listings", format=","),
            alt.Tooltip("listings:Q", title="All listings", format=","),
            alt.Tooltip("coverage:Q", title="Rating coverage", format=".1%"),
        ],
    )

    st.altair_chart(chart.properties(height=300), width="stretch")
    st.caption(f"{rated_count:,} of {len(eligible):,} eligible listings have a rating.")


def show_cleaning_impact(before, after):
    st.subheader("Cleaning impact")
    st.caption("Full-catalog comparison")
    removed = before.loc[~before["index"].isin(after["index"])]

    first, second, third = st.columns(3)
    first.metric("Original listings", f"{len(before):,}")
    second.metric("Cleaned listings", f"{len(after):,}")
    third.metric("Listings removed", f"{len(removed):,}")

    fields = ["product_name", "brand", "description", "rating"]
    summary = pd.DataFrame({
        "Field": ["Product name", "Brand", "Description", "Rating"],
        "Missing before": before[fields].isna().sum().tolist(),
        "Missing after": after[fields].isna().sum().tolist(),
        "Cleaning decision": [
            "Remove listings with no product name",
            "Fill blanks with Unknown",
            "Fill blanks with Not Available",
            "Exclude missing ratings from averages",
        ],
    })
    st.dataframe(summary, hide_index=True, width="stretch")

    st.subheader("Inspect a cleaning change")
    example = st.selectbox(
        "Choose an example",
        ["Missing description", "Missing brand", "Removed listing"],
    )

    if example == "Removed listing":
        if removed.empty:
            st.info("No removed listings were found.")
            return
        row = removed.iloc[0]
        st.write(f"**Listing #{row['index']}** · {row['category']}")
        before_value = row["product_name"] if pd.notna(row["product_name"]) else "Blank product name"
        after_value = "Listing removed"
    else:
        field = "description" if example == "Missing description" else "brand"
        blanks = before.loc[before[field].isna(), ["index", "product_name"]]
        examples = blanks.merge(
            after[["index", field]].dropna(subset=[field]), on="index"
        )
        if examples.empty:
            st.info("No filled values were found for this field.")
            return
        row = examples.iloc[0]
        st.write(f"**{row['product_name']}** · Listing #{row['index']}")
        before_value, after_value = "Blank", row[field]

    left, right = st.columns(2)
    left.markdown("**Before cleaning**")
    left.write(before_value)
    right.markdown("**After cleaning**")
    right.write(after_value)


def show_catalog(catalog, category, budget, cleaned):
    products = catalog
    if category != ALL_CATEGORIES:
        products = products.loc[products["category"].eq(category)]
    if budget is not None:
        products = products.loc[products["sale_price"].between(0, budget)]
    if products.empty:
        st.info("No listings match your filters. Try another category or a higher budget.")
        return

    products = products.copy()
    sale = products["sale_price"].where(products["sale_price"].ge(0))
    market = products["market_price"].where(products["market_price"].gt(0))
    products["discount_pct"] = ((market - sale) / market * 100).round(1)

    median = sale.median()
    rated_count = products["rating"].count()
    average_rating = products["rating"].mean()
    first, second, third, fourth = st.columns(4)
    first.metric("Listings", f"{len(products):,}")
    second.metric("Median price", f"₹{median:,.2f}" if pd.notna(median) else "—")
    third.metric("Discounted listings", f"{sale.lt(market).sum():,}")
    fourth.metric("Average rating", f"{average_rating:.2f} / 5" if rated_count else "—")
    st.caption(f"Rating average uses {rated_count:,} of {len(products):,} listings.")

    show_group_comparison(products, category)
    show_price_chart(products)
    show_rating_chart(products)

    st.subheader("Product listings")
    table = products[list(TABLE_COLUMNS)].rename(columns=TABLE_COLUMNS).copy()
    if cleaned:
        table["Rating"] = table["Rating"].map(
            lambda rating: "Not rated" if pd.isna(rating) else f"{rating:.1f}"
        )

    st.dataframe(
        table,
        hide_index=True,
        width="stretch",
        column_config={
            "Description": st.column_config.TextColumn("Description", width="medium"),
            "Sale price (₹)": st.column_config.NumberColumn(format="%.2f"),
            "Market price (₹)": st.column_config.NumberColumn(format="%.2f"),
            "Discount (%)": st.column_config.NumberColumn(format="%.1f"),
        },
    )


def main():
    st.html(PAGE_HEADER)

    before = load_catalog("BigBasket Products.csv")
    after = load_catalog("BigBasket_Cleaned.csv")
    view = st.radio(
        "Dashboard view",
        ["After cleaning", "Before cleaning", "Cleaning impact"],
        horizontal=True,
    )

    st.sidebar.header("Catalog filters")
    st.sidebar.caption("Prices are shown in Indian rupees (₹).")
    st.sidebar.markdown(f"[Kaggle dataset]({KAGGLE_URL})")

    if view == "Cleaning impact":
        show_cleaning_impact(before, after)
        return

    cleaned = view == "After cleaning"
    catalog = after if cleaned else before
    categories = sorted(catalog["category"].dropna().unique())
    category = st.sidebar.selectbox("Category", [ALL_CATEGORIES, *categories])

    use_budget = st.sidebar.checkbox("Set a maximum sale price")
    price_limit = st.sidebar.number_input(
        "Maximum sale price (₹)",
        min_value=0.0,
        value=500.0,
        step=10.0,
        disabled=not use_budget,
    )
    show_catalog(catalog, category, price_limit if use_budget else None, cleaned)


if __name__ == "__main__":
    main()



