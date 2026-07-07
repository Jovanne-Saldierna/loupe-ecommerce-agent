from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from google.cloud import bigquery
import os
import streamlit as st
from google.oauth2 import service_account

PROJECT_ID = "ai-weekend-agent-501502"
DATASET = "bigquery-public-data.thelook_ecommerce"

# Paid vs. unpaid channel classification.
# ASSUMPTION: "Search" in this dataset represents organic/SEO search results,
# not paid search ads (there is no separate "Paid Search" value in the data).
# Facebook, Display, and Email are treated as paid/marketing-driven channels.
PAID_CHANNELS = ["Facebook", "Display", "Email"]
UNPAID_CHANNELS = ["Search", "Organic"]


def get_bq_client(project: str = PROJECT_ID) -> bigquery.Client:
    """Build a BigQuery client using Streamlit secrets in the cloud,
    falling back to local default credentials when running locally."""
    try:
        if "gcp_service_account" in st.secrets:
            credentials = service_account.Credentials.from_service_account_info(
                st.secrets["gcp_service_account"]
            )
            return bigquery.Client(project=project, credentials=credentials)
    except Exception:
        pass
    return bigquery.Client(project=project)


# ---------------------------------------------------------------------------
# Core metric queries
# ---------------------------------------------------------------------------

def get_category_metrics(category: str) -> str:
    """Pull revenue, margin, return rate, and volume for a single category,
    plus the company-wide blended benchmark for comparison."""
    client = get_bq_client()

    query = f"""
    SELECT
        p.category,
        SUM(oi.sale_price) AS revenue,
        SUM(oi.sale_price - p.cost) AS margin,
        COUNT(*) AS total_items,
        COUNTIF(oi.status = 'Returned') AS returned_items,
        ROUND(SAFE_DIVIDE(COUNTIF(oi.status = 'Returned'), COUNT(*)) * 100, 2) AS return_rate_pct
    FROM `{DATASET}.order_items` oi
    JOIN `{DATASET}.products` p ON oi.product_id = p.id
    WHERE p.category = @category
    GROUP BY p.category
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("category", "STRING", category)]
    )
    results = list(client.query(query, job_config=job_config).result())

    if not results:
        return f"No data found for category: {category}"

    row = results[0]
    benchmark = get_company_benchmark()

    return (
        f"Category: {row.category}\n"
        f"Revenue: ${row.revenue:,.0f}\n"
        f"Margin: ${row.margin:,.0f}\n"
        f"Total Items Sold: {row.total_items:,}\n"
        f"Returned Items: {row.returned_items:,}\n"
        f"Return Rate: {row.return_rate_pct}%\n\n"
        f"{benchmark}"
    )


def get_company_benchmark() -> str:
    """Company-wide blended averages for comparison context."""
    client = get_bq_client()
    query = f"""
    SELECT
        ROUND(SAFE_DIVIDE(SUM(oi.sale_price - p.cost), SUM(oi.sale_price)) * 100, 2) AS avg_margin_pct,
        ROUND(SAFE_DIVIDE(COUNTIF(oi.status = 'Returned'), COUNT(*)) * 100, 2) AS avg_return_rate_pct
    FROM `{DATASET}.order_items` oi
    JOIN `{DATASET}.products` p ON oi.product_id = p.id
    """
    row = list(client.query(query).result())[0]
    return (
        f"Company-wide Average Margin: {row.avg_margin_pct}%\n"
        f"Company-wide Average Return Rate: {row.avg_return_rate_pct}%"
    )


def get_multi_category_comparison(categories: list[str]) -> str:
    """Pull metrics for multiple categories and format as a comparison table."""
    client = get_bq_client()
    query = f"""
    SELECT
        p.category,
        SUM(oi.sale_price) AS revenue,
        SUM(oi.sale_price - p.cost) AS margin,
        COUNT(*) AS total_items,
        ROUND(SAFE_DIVIDE(COUNTIF(oi.status = 'Returned'), COUNT(*)) * 100, 2) AS return_rate_pct
    FROM `{DATASET}.order_items` oi
    JOIN `{DATASET}.products` p ON oi.product_id = p.id
    WHERE p.category IN UNNEST(@categories)
    GROUP BY p.category
    ORDER BY return_rate_pct ASC
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ArrayQueryParameter("categories", "STRING", categories)]
    )
    results = client.query(query, job_config=job_config).result()

    lines = ["Category | Revenue | Margin | Items Sold | Return Rate"]
    lines.append("---------|---------|--------|------------|------------")
    for row in results:
        lines.append(
            f"{row.category} | ${row.revenue:,.0f} | ${row.margin:,.0f} | "
            f"{row.total_items:,} | {row.return_rate_pct}%"
        )
    return "\n".join(lines)


def get_state_metrics(state: str) -> str:
    """Pull revenue, margin, return rate, and volume for a single state."""
    client = get_bq_client()
    query = f"""
    SELECT
        u.state,
        SUM(oi.sale_price) AS revenue,
        SUM(oi.sale_price - p.cost) AS margin,
        COUNT(*) AS total_items,
        ROUND(SAFE_DIVIDE(COUNTIF(oi.status = 'Returned'), COUNT(*)) * 100, 2) AS return_rate_pct
    FROM `{DATASET}.order_items` oi
    JOIN `{DATASET}.products` p ON oi.product_id = p.id
    JOIN `{DATASET}.users` u ON oi.user_id = u.id
    WHERE u.state = @state
    GROUP BY u.state
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("state", "STRING", state)]
    )
    results = list(client.query(query, job_config=job_config).result())

    if not results:
        return f"No data found for state: {state}"

    row = results[0]
    benchmark = get_company_benchmark()

    return (
        f"State: {row.state}\n"
        f"Revenue: ${row.revenue:,.0f}\n"
        f"Margin: ${row.margin:,.0f}\n"
        f"Total Items Sold: {row.total_items:,}\n"
        f"Return Rate: {row.return_rate_pct}%\n\n"
        f"{benchmark}"
    )


def get_multi_state_comparison(states: list[str]) -> str:
    """Pull metrics for multiple states and format as a comparison table."""
    client = get_bq_client()
    query = f"""
    SELECT
        u.state,
        SUM(oi.sale_price) AS revenue,
        SUM(oi.sale_price - p.cost) AS margin,
        COUNT(*) AS total_items,
        ROUND(SAFE_DIVIDE(COUNTIF(oi.status = 'Returned'), COUNT(*)) * 100, 2) AS return_rate_pct
    FROM `{DATASET}.order_items` oi
    JOIN `{DATASET}.products` p ON oi.product_id = p.id
    JOIN `{DATASET}.users` u ON oi.user_id = u.id
    WHERE u.state IN UNNEST(@states)
    GROUP BY u.state
    ORDER BY return_rate_pct ASC
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ArrayQueryParameter("states", "STRING", states)]
    )
    results = client.query(query, job_config=job_config).result()

    lines = ["State | Revenue | Margin | Items Sold | Return Rate"]
    lines.append("------|---------|--------|------------|------------")
    for row in results:
        lines.append(
            f"{row.state} | ${row.revenue:,.0f} | ${row.margin:,.0f} | "
            f"{row.total_items:,} | {row.return_rate_pct}%"
        )
    return "\n".join(lines)


def get_returns_leakage() -> str:
    """Rank all categories by total margin lost to returns, worst first."""
    client = get_bq_client()
    query = f"""
    SELECT
        p.category,
        COUNTIF(oi.status = 'Returned') AS returned_items,
        COUNT(*) AS total_items,
        ROUND(SAFE_DIVIDE(COUNTIF(oi.status = 'Returned'), COUNT(*)) * 100, 2) AS return_rate_pct,
        SUM(IF(oi.status = 'Returned', oi.sale_price - p.cost, 0)) AS margin_lost_to_returns
    FROM `{DATASET}.order_items` oi
    JOIN `{DATASET}.products` p ON oi.product_id = p.id
    GROUP BY p.category
    ORDER BY margin_lost_to_returns DESC
    """
    results = client.query(query).result()

    lines = ["Category | Return Rate | Returned Items | Margin Lost to Returns"]
    lines.append("---------|-------------|-----------------|------------------------")
    for row in results:
        lines.append(
            f"{row.category} | {row.return_rate_pct}% | {row.returned_items:,} | "
            f"${row.margin_lost_to_returns:,.0f}"
        )
    return "\n".join(lines)


def get_channel_mix_trend() -> str:
    """Pull trailing 24-month order volume by paid vs. unpaid traffic source."""
    client = get_bq_client()
    query = f"""
    SELECT
        FORMAT_DATE('%Y-%m', DATE(oi.created_at)) AS month,
        u.traffic_source,
        COUNT(*) AS order_count
    FROM `{DATASET}.order_items` oi
    JOIN `{DATASET}.users` u ON oi.user_id = u.id
    WHERE DATE(oi.created_at) >= DATE_SUB(CURRENT_DATE(), INTERVAL 24 MONTH)
    GROUP BY month, u.traffic_source
    ORDER BY month ASC
    """
    results = list(client.query(query).result())

    monthly = {}
    for row in results:
        monthly.setdefault(row.month, {"paid": 0, "unpaid": 0, "total": 0})
        if row.traffic_source in PAID_CHANNELS:
            monthly[row.month]["paid"] += row.order_count
        else:
            monthly[row.month]["unpaid"] += row.order_count
        monthly[row.month]["total"] += row.order_count

    lines = ["Month | Paid Orders | Unpaid Orders | Total Orders | Paid Share"]
    lines.append("------|-------------|---------------|--------------|------------")
    for month in sorted(monthly.keys()):
        m = monthly[month]
        paid_share = round((m["paid"] / m["total"]) * 100, 1) if m["total"] else 0
        lines.append(f"{month} | {m['paid']:,} | {m['unpaid']:,} | {m['total']:,} | {paid_share}%")

    note = (
        "\n\nNote: 'Paid' = Facebook, Display, Email. 'Unpaid' = Search, Organic. "
        "This dataset does not distinguish paid search from organic search results, "
        "so 'Search' is classified as unpaid."
    )
    return "\n".join(lines) + note


# ---------------------------------------------------------------------------
# Scenario simulation
# ---------------------------------------------------------------------------

LEVER_RULES = {
    "return_rate_improvement": {
        "description": "Sensitivity of category margin to a change in return rate",
        "rule": (
            "A return rate above roughly 20% is a significant margin drain for apparel e-commerce; "
            "below roughly 10% is considered healthy. If a category's return rate drops by N percentage "
            "points, recalculate the retained revenue and margin assuming the recovered items would have "
            "sold at the category's current average sale price and margin. The larger the point drop, the "
            "more material the retained margin, but returns rarely reach zero, so treat full elimination "
            "as unrealistic."
        ),
    },
    "channel_mix_shift": {
        "description": "Sensitivity of growth durability to paid vs. unpaid channel mix",
        "rule": (
            "An increasing paid-channel share of order volume signals growth that is more dependent on "
            "continued ad spend and more exposed to rising acquisition costs or budget cuts. An increasing "
            "unpaid (organic/direct) share signals more durable, self-sustaining growth that is less "
            "vulnerable to a marketing budget change."
        ),
    },
    "category_price_position": {
        "description": "Sensitivity of category resilience to its margin percentage relative to the company average",
        "rule": (
            "A category with a margin percentage below the company-wide average has less room to absorb "
            "cost inflation, supplier price increases, or discount promotions before becoming unprofitable. "
            "A category priced above the company average has more cushion to withstand those same pressures."
        ),
    },
}


def get_lever_baseline(lever: str, category: str = None) -> str:
    """Pull the real current baseline data relevant to a specific lever."""
    client = get_bq_client()

    if lever == "return_rate_improvement":
        if not category:
            return "No category specified for return rate scenario."
        return get_category_metrics(category)

    elif lever == "channel_mix_shift":
        return get_channel_mix_trend()

    elif lever == "category_price_position":
        if not category:
            return "No category specified for price position scenario."
        query = f"""
        SELECT
            p.category,
            ROUND(AVG(oi.sale_price), 2) AS avg_sale_price,
            ROUND(AVG(p.cost), 2) AS avg_cost,
            ROUND(SAFE_DIVIDE(SUM(oi.sale_price - p.cost), SUM(oi.sale_price)) * 100, 2) AS margin_pct
        FROM `{DATASET}.order_items` oi
        JOIN `{DATASET}.products` p ON oi.product_id = p.id
        WHERE p.category = @category
        GROUP BY p.category
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("category", "STRING", category)]
        )
        results = list(client.query(query, job_config=job_config).result())
        if not results:
            return f"No data found for category: {category}"
        row = results[0]
        benchmark = get_company_benchmark()
        return (
            f"Category: {row.category}\n"
            f"Average Sale Price: ${row.avg_sale_price}\n"
            f"Average Cost: ${row.avg_cost}\n"
            f"Margin Percentage: {row.margin_pct}%\n\n"
            f"{benchmark}"
        )

    else:
        return "No baseline data available for this lever."


# ---------------------------------------------------------------------------
# Model + prompts
# ---------------------------------------------------------------------------

load_dotenv()
try:
    if "ANTHROPIC_API_KEY" in st.secrets:
        os.environ["ANTHROPIC_API_KEY"] = st.secrets["ANTHROPIC_API_KEY"]
except Exception:
    pass

model = ChatAnthropic(model="claude-sonnet-4-6")

category_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are a business analytics assistant for an e-commerce company.
You will be given real, calculated metrics for a specific product category, along with company-wide blended benchmarks for comparison.

Write your response using this exact structure with markdown headers:

## [Category] Performance Summary
One sentence stating the overall takeaway.

### Key Highlights:
- **Profitability:** compare the category's margin to the company-wide average margin percentage, explain what it means
- **Returns:** compare the category's return rate to the company-wide average, explain what it means
- **Volume:** reference total items sold and what it suggests about scale

### Recommendation:
A clear recommendation on whether this category warrants increased, maintained, or reduced investment, grounded only in the numbers provided.

Do not invent numbers. Only use the metrics provided below.

Metrics:
{metrics}"""),
    ("user", "{question}")
])
category_chain = category_prompt | model

comparison_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are a business analytics assistant for an e-commerce company.
Compare these entities using real metrics only. Do not use emoji.
Use a measured, executive tone, directional and evidence-based rather than alarmist.
When determining "best" or "worst" performer, weight return rate heavily: a high return rate erodes margin even when revenue looks strong, so a low-return, high-margin entity should generally outrank a high-revenue, high-return entity.
You have no knowledge of what the full dataset contains beyond the metrics provided below. If the question asks about an entity not present in the metrics below, do not speculate about why, do not claim it is missing from the dataset, and do not state anything about data availability. Simply compare only the entities actually present in the metrics.

Structure your response with markdown headers. Do not repeat the raw data table, it will be shown separately.

Metrics:
{metrics}"""),
    ("user", "{question}")
])
comparison_chain = comparison_prompt | model

scenario_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are a business analytics assistant for an e-commerce company.
You will be given:
1. The real current baseline data for a specific business lever
2. A documented sensitivity rule for how that lever affects business performance
3. A hypothetical scenario someone wants to explore

Apply the documented rule to the hypothetical, using the real baseline as context.
Do not invent new reasoning outside the documented rule. Be direct and executive-ready.

Baseline Data:
{baseline}

Documented Rule:
{rule}"""),
    ("user", "{scenario}")
])
scenario_chain = scenario_prompt | model

channel_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are a business analytics assistant for an e-commerce company.
You will be given real month-by-month order volume data split between paid and unpaid traffic sources over a trailing 24-month window.

Your job:
- Identify specific months where paid share notably increased or decreased
- State whether total order volume moved proportionally with paid share in those months
- Conclude what this suggests about how dependent order growth is on paid channels versus organic/direct demand
- Do not invent numbers. Only reference the data provided.

Data:
{channel_data}"""),
    ("user", "{question}")
])
channel_chain = channel_prompt | model

leakage_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are a business analytics assistant for an e-commerce company.
You will be given a table ranking every product category by how much margin is being lost to returns, worst first.

Your job:
- Identify the top 3-5 categories losing the most margin to returns specifically, not just the ones with the highest return rate percentage, since a smaller category with a high rate may lose less absolute margin than a large category with a moderate rate
- Distinguish between a high return rate (an operational/quality problem) and high absolute margin lost (a financial impact problem), since these don't always point to the same category
- Give a clear, prioritized recommendation on which categories deserve investigation first
- Do not invent numbers. Only reference the data provided.

Data:
{leakage_data}"""),
    ("user", "{question}")
])
leakage_chain = leakage_prompt | model

router_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are a routing assistant. Classify the user's question into exactly ONE of these categories:

- single_category: asking about one specific product category's performance
- multi_category_comparison: asking to compare multiple specific product categories
- single_state: asking about one specific state's performance
- multi_state_comparison: asking to compare multiple specific states
- scenario_simulation: asking a hypothetical "what if" question about a specific lever (return rate, channel mix, category pricing/margin)
- channel_analysis: asking whether order growth is driven by paid marketing channels versus organic/direct traffic, or about the relationship between paid channel share and order volume over time
- returns_leakage: asking which categories are losing the most money or margin to returns, or asking for a ranked view of return-driven losses across categories
- general: anything else, including questions about the data itself

Respond with ONLY the category name, nothing else."""),
    ("user", "{question}")
])
router_chain = router_prompt | model


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

def simulate_scenario(lever: str, hypothetical: str, category: str = None) -> str:
    baseline = get_lever_baseline(lever, category=category)
    rule = LEVER_RULES[lever]["rule"]
    response = scenario_chain.invoke({
        "baseline": baseline,
        "rule": rule,
        "scenario": hypothetical
    })
    return response.content


def run_agent(question: str) -> dict:
    """Route a natural-language question to the correct capability."""
    category = router_chain.invoke({"question": question}).content.strip().lower()
    print(f"[Router decided: {category}]")

    if category == "single_category":
        extract_prompt = ChatPromptTemplate.from_messages([
            ("system", "Extract the single product category mentioned in this question. Respond with ONLY the category name, matching one of these exactly: Accessories, Active, Blazers & Jackets, Clothing Sets, Dresses, Fashion Hoodies & Sweatshirts, Intimates, Jeans, Jumpsuits & Rompers, Leggings, Maternity, Outerwear & Coats, Pants, Pants & Capris, Plus, Shorts, Skirts, Sleep & Lounge, Socks, Socks & Hosiery, Suits, Suits & Sport Coats, Sweaters, Swim, Tops & Tees, Underwear."),
            ("user", "{question}")
        ])
        cat_name = (extract_prompt | model).invoke({"question": question}).content.strip()

        metrics = get_category_metrics(cat_name)
        answer = category_chain.invoke({"metrics": metrics, "question": question}).content
        return {"category": category, "raw_data": metrics, "answer": answer}

    elif category == "multi_category_comparison":
        extract_prompt = ChatPromptTemplate.from_messages([
            ("system", "Extract every product category mentioned in this question, regardless of capitalization or phrasing. Respond with ONLY a comma-separated list of exact category names matching this list: Accessories, Active, Blazers & Jackets, Clothing Sets, Dresses, Fashion Hoodies & Sweatshirts, Intimates, Jeans, Jumpsuits & Rompers, Leggings, Maternity, Outerwear & Coats, Pants, Pants & Capris, Plus, Shorts, Skirts, Sleep & Lounge, Socks, Socks & Hosiery, Suits, Suits & Sport Coats, Sweaters, Swim, Tops & Tees, Underwear."),
            ("user", "{question}")
        ])
        cats_raw = (extract_prompt | model).invoke({"question": question}).content.strip()
        categories = [c.strip() for c in cats_raw.split(",") if c.strip()]

        if len(categories) < 2:
            return {
                "category": category,
                "raw_data": None,
                "answer": "I can compare specific categories, but I need at least two named categories to do that. Try naming them directly, for example: 'Compare Dresses, Jeans, and Swim.'"
            }

        metrics = get_multi_category_comparison(categories)
        answer = comparison_chain.invoke({"metrics": metrics, "question": question}).content
        return {"category": category, "raw_data": metrics, "answer": answer}

    elif category == "single_state":
        extract_prompt = ChatPromptTemplate.from_messages([
            ("system", "Extract the single US state mentioned in this question. Respond with ONLY the full state name as it would appear in a US address (e.g. California, Texas, New York)."),
            ("user", "{question}")
        ])
        state_name = (extract_prompt | model).invoke({"question": question}).content.strip()

        metrics = get_state_metrics(state_name)
        answer = category_chain.invoke({"metrics": metrics, "question": question}).content
        return {"category": category, "raw_data": metrics, "answer": answer}

    elif category == "multi_state_comparison":
        extract_prompt = ChatPromptTemplate.from_messages([
            ("system", "Extract every US state mentioned in this question, regardless of capitalization or phrasing. Respond with ONLY a comma-separated list of full state names, e.g. California,Texas,New York."),
            ("user", "{question}")
        ])
        states_raw = (extract_prompt | model).invoke({"question": question}).content.strip()
        states = [s.strip() for s in states_raw.split(",") if s.strip()]

        if len(states) < 2:
            return {
                "category": category,
                "raw_data": None,
                "answer": "I can compare specific states, but I need at least two named states to do that. Try naming them directly, for example: 'Compare California, Texas, and New York.'"
            }

        metrics = get_multi_state_comparison(states)
        answer = comparison_chain.invoke({"metrics": metrics, "question": question}).content
        return {"category": category, "raw_data": metrics, "answer": answer}

    elif category == "scenario_simulation":
        lever_prompt = ChatPromptTemplate.from_messages([
            ("system", f"Identify which ONE lever this question is about. Options: {', '.join(LEVER_RULES.keys())}. Respond with ONLY the lever name."),
            ("user", "{question}")
        ])
        lever = (lever_prompt | model).invoke({"question": question}).content.strip()

        cat_for_scenario = None
        if lever in ("return_rate_improvement", "category_price_position"):
            extract_prompt = ChatPromptTemplate.from_messages([
                ("system", "Extract the single product category mentioned in this question, if any. Respond with ONLY the category name matching this list, or NONE if no category is mentioned: Accessories, Active, Blazers & Jackets, Clothing Sets, Dresses, Fashion Hoodies & Sweatshirts, Intimates, Jeans, Jumpsuits & Rompers, Leggings, Maternity, Outerwear & Coats, Pants, Pants & Capris, Plus, Shorts, Skirts, Sleep & Lounge, Socks, Socks & Hosiery, Suits, Suits & Sport Coats, Sweaters, Swim, Tops & Tees, Underwear."),
                ("user", "{question}")
            ])
            cat_extracted = (extract_prompt | model).invoke({"question": question}).content.strip()
            cat_for_scenario = None if cat_extracted.upper() == "NONE" else cat_extracted

        baseline = get_lever_baseline(lever, category=cat_for_scenario)
        answer = simulate_scenario(lever, question, category=cat_for_scenario)
        return {"category": category, "raw_data": baseline, "answer": answer}

    elif category == "channel_analysis":
        channel_data = get_channel_mix_trend()
        answer = channel_chain.invoke({"channel_data": channel_data, "question": question}).content
        return {"category": category, "raw_data": channel_data, "answer": answer}

    elif category == "returns_leakage":
        leakage_data = get_returns_leakage()
        answer = leakage_chain.invoke({"leakage_data": leakage_data, "question": question}).content
        return {"category": category, "raw_data": leakage_data, "answer": answer}

    else:
        return {"category": "general", "raw_data": None, "answer": "This question falls outside my current capabilities."}

# ---------------------------------------------------------------------------
# Dashboard queries (parameterized by date range and optional filters)
# ---------------------------------------------------------------------------

STATE_ABBREV = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR", "California": "CA",
    "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE", "Florida": "FL", "Georgia": "GA",
    "Hawaii": "HI", "Idaho": "ID", "Illinois": "IL", "Indiana": "IN", "Iowa": "IA",
    "Kansas": "KS", "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME", "Maryland": "MD",
    "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN", "Mississippi": "MS",
    "Missouri": "MO", "Montana": "MT", "Nebraska": "NE", "Nevada": "NV",
    "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY",
    "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK",
    "Oregon": "OR", "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC",
    "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX", "Utah": "UT",
    "Vermont": "VT", "Virginia": "VA", "Washington": "WA", "West Virginia": "WV",
    "Wisconsin": "WI", "Wyoming": "WY", "District of Columbia": "DC",
}


def _build_filters(start_date, end_date, categories=None, states=None, alias_products="p", alias_users="u"):
    """Shared filter/param builder for dashboard queries."""
    filters = ["DATE(oi.created_at) BETWEEN @start_date AND @end_date"]
    params = [
        bigquery.ScalarQueryParameter("start_date", "DATE", start_date),
        bigquery.ScalarQueryParameter("end_date", "DATE", end_date),
    ]
    join_users = False
    if categories:
        filters.append(f"{alias_products}.category IN UNNEST(@categories)")
        params.append(bigquery.ArrayQueryParameter("categories", "STRING", categories))
    if states:
        filters.append(f"{alias_users}.state IN UNNEST(@states)")
        params.append(bigquery.ArrayQueryParameter("states", "STRING", states))
        join_users = True
    return " AND ".join(filters), params, join_users


def get_dashboard_kpis(start_date, end_date, categories=None, states=None) -> dict:
    """Top-line KPIs for the dashboard, filtered by date range and optional category/state."""
    client = get_bq_client()
    where_clause, params, join_users = _build_filters(start_date, end_date, categories, states)
    join_clause = f"JOIN `{DATASET}.users` u ON oi.user_id = u.id" if join_users else ""

    query = f"""
    SELECT
        SUM(oi.sale_price) AS revenue,
        SUM(oi.sale_price - p.cost) AS margin,
        COUNT(*) AS total_items,
        COUNTIF(oi.status = 'Returned') AS returned_items,
        ROUND(SAFE_DIVIDE(COUNTIF(oi.status = 'Returned'), COUNT(*)) * 100, 2) AS return_rate_pct
    FROM `{DATASET}.order_items` oi
    JOIN `{DATASET}.products` p ON oi.product_id = p.id
    {join_clause}
    WHERE {where_clause}
    """
    job_config = bigquery.QueryJobConfig(query_parameters=params)
    row = list(client.query(query, job_config=job_config).result())[0]
    return {
        "revenue": row.revenue or 0,
        "margin": row.margin or 0,
        "total_items": row.total_items or 0,
        "returned_items": row.returned_items or 0,
        "return_rate_pct": row.return_rate_pct or 0,
    }


def get_revenue_trend(start_date, end_date, categories=None, states=None) -> list[dict]:
    """Monthly revenue/margin/volume trend, filtered."""
    client = get_bq_client()
    where_clause, params, join_users = _build_filters(start_date, end_date, categories, states)
    join_clause = f"JOIN `{DATASET}.users` u ON oi.user_id = u.id" if join_users else ""

    query = f"""
    SELECT
        FORMAT_DATE('%Y-%m', DATE(oi.created_at)) AS month,
        SUM(oi.sale_price) AS revenue,
        SUM(oi.sale_price - p.cost) AS margin,
        COUNT(*) AS items
    FROM `{DATASET}.order_items` oi
    JOIN `{DATASET}.products` p ON oi.product_id = p.id
    {join_clause}
    WHERE {where_clause}
    GROUP BY month
    ORDER BY month ASC
    """
    job_config = bigquery.QueryJobConfig(query_parameters=params)
    results = client.query(query, job_config=job_config).result()
    return [{"month": r.month, "revenue": r.revenue, "margin": r.margin, "items": r.items} for r in results]


def get_category_leaderboard_dashboard(start_date, end_date, states=None) -> list[dict]:
    """All categories with revenue, margin, return rate, filtered by date/state."""
    client = get_bq_client()
    where_clause, params, join_users = _build_filters(start_date, end_date, categories=None, states=states)
    join_clause = f"JOIN `{DATASET}.users` u ON oi.user_id = u.id" if join_users else ""

    query = f"""
    SELECT
        p.category,
        SUM(oi.sale_price) AS revenue,
        SUM(oi.sale_price - p.cost) AS margin,
        COUNT(*) AS items,
        ROUND(SAFE_DIVIDE(COUNTIF(oi.status = 'Returned'), COUNT(*)) * 100, 2) AS return_rate_pct
    FROM `{DATASET}.order_items` oi
    JOIN `{DATASET}.products` p ON oi.product_id = p.id
    {join_clause}
    WHERE {where_clause}
    GROUP BY p.category
    ORDER BY revenue DESC
    """
    job_config = bigquery.QueryJobConfig(query_parameters=params)
    results = client.query(query, job_config=job_config).result()
    return [
        {
            "category": r.category, "revenue": r.revenue, "margin": r.margin,
            "items": r.items, "return_rate_pct": r.return_rate_pct,
        }
        for r in results
    ]


def get_state_breakdown_dashboard(start_date, end_date, categories=None) -> list[dict]:
    """All states with revenue, margin, order volume, filtered by date/category."""
    client = get_bq_client()
    where_clause, params, _ = _build_filters(start_date, end_date, categories=categories, states=None)
    params_with_users = params  # state join always needed here

    query = f"""
    SELECT
        u.state,
        SUM(oi.sale_price) AS revenue,
        SUM(oi.sale_price - p.cost) AS margin,
        COUNT(*) AS items
    FROM `{DATASET}.order_items` oi
    JOIN `{DATASET}.products` p ON oi.product_id = p.id
    JOIN `{DATASET}.users` u ON oi.user_id = u.id
    WHERE {where_clause}
    GROUP BY u.state
    ORDER BY revenue DESC
    """
    job_config = bigquery.QueryJobConfig(query_parameters=params_with_users)
    results = client.query(query, job_config=job_config).result()
    return [
        {
            "state": r.state, "state_abbrev": STATE_ABBREV.get(r.state, ""),
            "revenue": r.revenue, "margin": r.margin, "items": r.items,
        }
        for r in results
    ]


def get_channel_mix_range(start_date, end_date, categories=None, states=None) -> list[dict]:
    """Monthly paid vs. unpaid order mix, filtered by date range and optional category/state."""
    client = get_bq_client()
    where_clause, params, join_users = _build_filters(start_date, end_date, categories, states)
    # channel analysis always needs the users join for traffic_source, even if no state filter
    join_clause = f"JOIN `{DATASET}.users` u ON oi.user_id = u.id" if not join_users else f"JOIN `{DATASET}.users` u ON oi.user_id = u.id"

    query = f"""
    SELECT
        FORMAT_DATE('%Y-%m', DATE(oi.created_at)) AS month,
        u.traffic_source,
        COUNT(*) AS order_count
    FROM `{DATASET}.order_items` oi
    JOIN `{DATASET}.products` p ON oi.product_id = p.id
    {join_clause}
    WHERE {where_clause}
    GROUP BY month, u.traffic_source
    ORDER BY month ASC
    """
    job_config = bigquery.QueryJobConfig(query_parameters=params)
    results = list(client.query(query, job_config=job_config).result())

    monthly = {}
    for row in results:
        monthly.setdefault(row.month, {"paid": 0, "unpaid": 0, "total": 0})
        if row.traffic_source in PAID_CHANNELS:
            monthly[row.month]["paid"] += row.order_count
        else:
            monthly[row.month]["unpaid"] += row.order_count
        monthly[row.month]["total"] += row.order_count

    return [
        {"month": m, "paid": v["paid"], "unpaid": v["unpaid"], "total": v["total"]}
        for m, v in sorted(monthly.items())
    ]



if __name__ == "__main__":
    questions = [
        "How is the Dresses category performing?",
        "Compare Jeans, Swim, and Outerwear & Coats",
        "How is California performing?",
        "Compare California, Texas, and New York",
        "What if we cut the return rate in Swim by 5 points?",
        "Is our order growth driven by paid channels or organic traffic?",
        "Which categories are losing the most money to returns?",
    ]
    for q in questions:
        print(f"\n=== QUESTION: {q} ===")
        result = run_agent(q)
        print(result["answer"])