
> This is the original Streamlit version of Loupe. The current Loupe AI Analytics Platform expands this prototype into a full analytics operating layer: Commerce Intelligence, Metric Governance, and Data Quality Triage.

## Evolution: Loupe AI Platform

Loupe OG was the original Streamlit proof-of-concept for the core assistant workflow: ask a plain-English commerce question, query governed warehouse data, and return a grounded business answer.

The project has since expanded into the **Loupe AI Analytics Platform**, a three-layer analytics operating system covering business performance, metric trust, and data reliability.

### Current platform apps

| Layer | App | Purpose |
|---|---|---|
| Business Performance | Loupe Commerce Intelligence | Answers plain-English commerce questions and surfaces executive performance insights. |
| BI Trust | Metric Governance Copilot | Reviews SQL, validates governed metric definitions, shows definition drift, and produces steward summaries. |
| Engineering Reliability | Data Quality Incident Triage | Detects data-quality issues, generates AI triage playbooks, provides SQL sandbox debugging, and maps downstream impact. |

**Current platform repo:** [Loupe AI Analytics Platform](https://github.com/Jovanne-Saldierna/loupe-platform)

**Live apps:**
- [Loupe Commerce Intelligence](https://loupe-web-eight.vercel.app/)
- [Metric Governance Copilot](https://governance-web-opal.vercel.app/)
- [Data Quality Incident Triage](https://triage-web-eight.vercel.app/)

**Live app:** [loupe-ecommerce-agent.streamlit.app](https://loupe-ecommerce-agent.streamlit.app)

Loupe is an AI analytics agent and interactive dashboard built on real e-commerce order, product, and traffic data. Ask a plain-English question and get a grounded, numbers-first answer, not a guess, every response is generated fresh against live BigQuery data.

This project extends a pattern I originally built for a take-home case study into something fully generalized: same architecture, same validation discipline, applied to a public dataset so anyone can see it work end to end.

## Why I Built This

I wanted a second, public proof point for a specific skill: turning a one-time analysis into a reusable, governed capability instead of a static report. The first version of this pattern was built against a company's proprietary case study data during an interview process. This version rebuilds the same architecture from scratch against `bigquery-public-data.thelook_ecommerce`, a fully public dataset, so the whole thing, code included, can be public too.

## What It Does

Loupe has two parts: a conversational agent and a filterable dashboard.

**Ask the Agent** supports six capabilities:

- **Category performance** — "How is the Dresses category performing?" Profiles revenue, margin, and return rate against the company-wide benchmark.
- **Category comparison** — "Compare Jeans, Swim, and Outerwear & Coats." Compares named categories side by side, with return rate weighted heavily so a low price never masks a high-return problem.
- **State performance & comparison** — "Compare California, Texas, and New York." Same discipline, applied geographically.
- **Scenario simulation** — "What if we cut the return rate in Swim by 5 points?" Applies documented, real retail sensitivity rules to a hypothetical, grounded in the actual current baseline.
- **Channel mix analysis** — "Is our order growth driven by paid channels or organic traffic?" Tracks paid vs. unpaid traffic share over a trailing 24-month window to test whether growth is spend-dependent or organic.
- **Returns & margin leakage** — "Which categories are losing the most money to returns?" Ranks categories by absolute margin lost to returns, not just return rate, since a smaller category with a high rate can lose less money than a large category with a moderate one.

**Dashboard** adds a fully filterable view: date range, category, and state filters driving live KPIs, a revenue/margin trend line, a sortable category leaderboard, a state-level revenue choropleth, and a paid/unpaid channel mix chart.

## Architecture

- **Data:** `bigquery-public-data.thelook_ecommerce`, queried live and directly, no local copy or cache of the underlying data.
- **Orchestration:** LangChain, with a routing chain classifying each question into one of six capabilities plus a general fallback, and dedicated extraction chains pulling structured entities (category names, state names, scenario levers) out of natural language.
- **Model:** Claude (Anthropic), via `langchain-anthropic`.
- **Interface:** Streamlit, with a custom design system, a left icon-rail navigation, status pills (Healthy / Watch / Risk) applied consistently to every return-rate figure across the app, and a live choropleth map.
- **Query safety:** every BigQuery query is parameterized, never string-interpolated.
- **Deployment:** Streamlit Community Cloud, authenticated via a dedicated GCP service account scoped to read-only BigQuery access.

## Design Principles

- Every answer is grounded only in real numbers pulled live from the dataset. The agent is instructed never to invent figures or speculate about data it wasn't given.
- "Best performer" logic explicitly penalizes a high return rate, so a low acquisition cost or low price never outweighs a real margin problem.
- Scenario simulations apply documented, defensible retail logic (a return rate above ~20% is a significant margin drain, a category's margin percentage relative to the company average signals its resilience to cost pressure), not invented reasoning.
- Every capability was tested against manually recalculated numbers before being finalized.

## Running It Locally

```bash
git clone https://github.com/Jovanne-Saldierna/loupe-ecommerce-agent.git
cd loupe-ecommerce-agent
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file in the project root containing your Anthropic API key, in the form: `ANTHROPIC_API_KEY=your_key_here`
You'll also need a GCP project with BigQuery access (the dataset itself is public, but querying it requires a project for billing/quota) and local Google Cloud authentication (`gcloud auth application-default login`) or a service account key.

```bash
streamlit run app.py
```

## What's Next

- Automatic full-dataset ranking for open-ended "best/worst overall" questions, without requiring named entities
- A full LangGraph implementation with an explicit human-in-the-loop checkpoint before any recommendation is treated as final
- LangSmith tracing on every run for production-grade auditability

## About Me

I'm Jovanne Saldierna, a data analyst with an honest interest in AI-assistance. This project reflects the same instinct I apply to all my work: validate everything, ground every claim in real data, and turn one-time analysis into governed, reusable tooling, now applied to AI-assisted workflows instead of just dashboards.

- Email: JovanneSaldierna1@gmail.com
- Phone: 443-466-5476
- GitHub: [github.com/Jovanne-Saldierna](https://github.com/Jovanne-Saldierna)

## License

MIT
