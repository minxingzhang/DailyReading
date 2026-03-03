import os
import yaml
from datetime import datetime, timezone
from anthropic import Anthropic
from scripts.fetch_papers import fetch_arxiv_papers, fetch_hf_papers, merge_and_deduplicate
from scripts.score_papers import select_top_papers
from scripts.generate_analysis import generate_analysis
from scripts.render_html import (
    render_daily_page, render_index_page, render_email_html,
    write_daily_page, write_index_page,
)
from scripts.send_email import send_digest_email


def load_config(config_path: str = "config.yaml") -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def run_pipeline(
    docs_dir: str,
    anthropic_api_key: str,
    gmail_user: str,
    gmail_password: str,
    email_recipients: list,
    base_url: str,
    config_path: str = "config.yaml",
) -> None:
    config = load_config(config_path)
    client = Anthropic(api_key=anthropic_api_key)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    print(f"[DailyPaper] Starting pipeline for {today}")

    print("Fetching HuggingFace daily papers...")
    hf_papers = fetch_hf_papers()
    print(f"  Found {len(hf_papers)} HF papers")

    categories_data = []
    for cat_id, cat_cfg in config["categories"].items():
        print(f"\nProcessing: {cat_cfg['name_en']}")

        arxiv_papers = fetch_arxiv_papers(
            keywords=cat_cfg["keywords"],
            arxiv_categories=cat_cfg["arxiv_categories"],
            lookback_hours=config["schedule"]["lookback_hours"],
        )
        print(f"  arXiv candidates: {len(arxiv_papers)}")

        hf_relevant = [
            p for p in hf_papers
            if any(kw.lower() in (p.title + p.abstract).lower() for kw in cat_cfg["keywords"])
        ]

        candidates = merge_and_deduplicate([arxiv_papers, hf_relevant])
        max_cands = config["llm"]["max_candidates_per_category"]
        candidates = candidates[:max_cands]
        print(f"  Total candidates: {len(candidates)}")

        if not candidates:
            print(f"  WARNING: No candidates found for {cat_cfg['name_en']}")
            categories_data.append({
                "id": cat_id,
                "name_zh": cat_cfg["name_zh"],
                "name_en": cat_cfg["name_en"],
                "analyses": [],
            })
            continue

        top_papers = select_top_papers(
            candidates,
            category_name=cat_cfg["name_en"],
            category_type=cat_cfg["type"],
            n=cat_cfg["papers_per_day"],
            client=client,
        )
        print(f"  Selected {len(top_papers)} papers")

        analyses = []
        for sp in top_papers:
            print(f"    Analyzing: {sp.paper.title[:60]}...")
            analysis = generate_analysis(sp, client)
            analyses.append(analysis)

        categories_data.append({
            "id": cat_id,
            "name_zh": cat_cfg["name_zh"],
            "name_en": cat_cfg["name_en"],
            "analyses": analyses,
        })

    # Render and save daily page
    site_cfg = config.get("site", {})
    daily_html = render_daily_page(today, categories_data, base_url, site_cfg.get("title", "DailyPaper"))
    write_daily_page(today, daily_html, docs_dir)
    print(f"\nWrote: docs/{today}/index.html")

    # Update index with archive
    archive_dates = sorted(
        [d for d in os.listdir(docs_dir)
         if os.path.isdir(os.path.join(docs_dir, d)) and not d.startswith(".")],
        reverse=True,
    )
    index_html = render_index_page(archive_dates, latest_date=today, base_url=base_url)
    write_index_page(index_html, docs_dir)
    print("Updated: docs/index.html")

    # Send email
    if email_recipients:
        full_url = f"{base_url}/{today}/" if base_url else f"/{today}/"
        email_html = render_email_html(today, categories_data, full_url)
        email_cfg = config.get("email", {})
        send_digest_email(
            date=today,
            html_body=email_html,
            gmail_user=gmail_user,
            gmail_password=gmail_password,
            recipients=email_recipients,
            subject_prefix=email_cfg.get("subject_prefix", "[DailyPaper]"),
        )
        print(f"Email sent to: {email_recipients}")
    else:
        print("No email recipients configured, skipping email.")

    print("\n[DailyPaper] Pipeline complete!")


if __name__ == "__main__":
    run_pipeline(
        docs_dir=os.path.join(os.path.dirname(os.path.dirname(__file__)), "docs"),
        anthropic_api_key=os.environ["ANTHROPIC_API_KEY"],
        gmail_user=os.environ.get("GMAIL_USER", ""),
        gmail_password=os.environ.get("GMAIL_APP_PASSWORD", ""),
        email_recipients=[
            r.strip() for r in os.environ.get("EMAIL_RECIPIENTS", "").split(",") if r.strip()
        ],
        base_url=os.environ.get("SITE_BASE_URL", ""),
    )
