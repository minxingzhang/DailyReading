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
from scripts.seen_papers import load_seen_ids, save_seen_ids, filter_new_papers, mark_papers_as_seen


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
    seen_papers_path: str = None,
) -> None:
    config = load_config(config_path)
    client = Anthropic(api_key=anthropic_api_key)
    # Use Beijing date (UTC+8) for display and dedup key
    from datetime import timedelta
    today = (datetime.now(timezone.utc) + timedelta(hours=8)).strftime("%Y-%m-%d")

    if seen_papers_path is None:
        seen_papers_path = os.path.join(
            os.path.dirname(os.path.abspath(config_path)), "data", "seen_papers.json"
        )

    print(f"[DailyPaper] Starting pipeline for {today} (Beijing)")

    # Load seen paper IDs once — O(1) lookups for all subsequent checks
    seen_ids = load_seen_ids(seen_papers_path)
    print(f"  Loaded {len(seen_ids)} previously seen paper IDs")

    print("Fetching HuggingFace daily papers...")
    hf_papers = fetch_hf_papers()
    print(f"  Found {len(hf_papers)} HF papers")

    categories_data = []
    all_selected_papers = []  # accumulate for marking as seen after pipeline succeeds

    for cat_id, cat_cfg in config["categories"].items():
        print(f"\nProcessing: {cat_cfg['name_en']}")

        arxiv_papers = fetch_arxiv_papers(
            keywords=cat_cfg["keywords"],
            arxiv_categories=cat_cfg["arxiv_categories"],
            lookback_hours=config["schedule"]["lookback_hours"],
        )
        print(f"  arXiv candidates: {len(arxiv_papers)}")

        # Fallback: extend lookback if too few raw candidates (prefer new papers, but better than none)
        if len(arxiv_papers) < cat_cfg["papers_per_day"]:
            fallback_hours = config["schedule"].get("fallback_lookback_hours", 168)
            extended = fetch_arxiv_papers(
                keywords=cat_cfg["keywords"],
                arxiv_categories=cat_cfg["arxiv_categories"],
                lookback_hours=fallback_hours,
            )
            if len(extended) > len(arxiv_papers):
                arxiv_papers = extended
                print(f"  Extended lookback to {fallback_hours}h: {len(arxiv_papers)} candidates")

        hf_relevant = [
            p for p in hf_papers
            if any(kw.lower() in (p.title + p.abstract).lower() for kw in cat_cfg["keywords"])
        ]

        candidates = merge_and_deduplicate([arxiv_papers, hf_relevant])

        # Remove papers already pushed in previous runs
        candidates = filter_new_papers(candidates, seen_ids)
        print(f"  After dedup: {len(candidates)} new candidates")

        max_cands = config["llm"]["max_candidates_per_category"]
        candidates = candidates[:max_cands]

        if not candidates:
            print(f"  WARNING: No new candidates for {cat_cfg['name_en']} (all already seen)")
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
            all_selected_papers.append(sp.paper)

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

    # Update index with archive (exclude non-date dirs like 'plans')
    archive_dates = sorted(
        [d for d in os.listdir(docs_dir)
         if os.path.isdir(os.path.join(docs_dir, d))
         and not d.startswith(".")
         and len(d) == 10 and d[4] == "-"],  # YYYY-MM-DD format only
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

    # Persist seen paper IDs only after the pipeline succeeds
    updated_seen = mark_papers_as_seen(all_selected_papers, seen_ids, today)
    save_seen_ids(updated_seen, seen_papers_path)
    print(f"Saved {len(updated_seen)} seen IDs to {seen_papers_path}")

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
