"""
Spotify Discovery Engine — Streamlit Frontend
Phase 5: Live demo dashboard
"""

import streamlit as st
import plotly.express as px
import pandas as pd
from graphviz import Digraph

from backend import run_live_demo, trigger_full_pipeline, load_insights

# --- Page config ---
st.set_page_config(
    page_title="Spotify Discovery Engine",
    page_icon="🎧",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# --- Theme styling ---
SPOTIFY_GREEN = "#1DB954"
DARK_BG = "#121212"
GREY = "#B3B3B3"

st.markdown(
    f"""
    <style>
    .stApp {{
        background-color: {DARK_BG};
        color: #ffffff;
    }}
    .stButton>button {{
        background-color: {SPOTIFY_GREEN};
        color: #ffffff;
        border: none;
        border-radius: 500px;
        padding: 0.75rem 2rem;
        font-weight: 700;
    }}
    .stButton>button:hover {{
        background-color: #1ed760;
        color: #ffffff;
    }}
    .review-card {{
        background-color: #181818;
        border-radius: 12px;
        padding: 1.25rem;
        margin-bottom: 1rem;
        border-left: 4px solid {SPOTIFY_GREEN};
    }}
    .tag {{
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 500px;
        font-size: 0.85rem;
        margin-right: 0.5rem;
        margin-bottom: 0.5rem;
        font-weight: 600;
    }}
    .tag-yes {{
        background-color: {SPOTIFY_GREEN};
        color: #ffffff;
    }}
    .tag-no {{
        background-color: #333333;
        color: {GREY};
    }}
    .tag-segment {{
        background-color: #2a2a2a;
        color: {SPOTIFY_GREEN};
        border: 1px solid {SPOTIFY_GREEN};
    }}
    .tag-frustration {{
        background-color: #2a2a2a;
        color: #ff6b6b;
        border: 1px solid #ff6b6b;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

# --- Header ---
st.title("🎧 Spotify Discovery Engine")
st.caption("Live demo of the discovery-frustration classifier")


# --- Helper: render review cards ---
def render_review_cards(reviews):
    """Render a list of review dicts as HTML cards."""
    html = ""
    for r in reviews:
        text = r["review_text"]
        if len(text) > 200:
            text = text[:200] + "..."

        discovery = r.get("discovery_related", False)
        discovery_tag = (
            '<span class="tag tag-yes">YES</span>'
            if discovery
            else '<span class="tag tag-no">NO</span>'
        )

        html += f"""
        <div class="review-card">
            <p style="color: #ffffff; margin-bottom: 0.75rem;">{text}</p>
            <div style="margin-bottom: 0.5rem;">
                <span class="tag tag-segment">{r.get('segment', 'unknown')}</span>
                <span class="tag tag-frustration">{r.get('frustration_type', 'none')}</span>
                <span class="tag tag-no">{'⭐' * int(r.get('rating', 0))}</span>
                {discovery_tag}
            </div>
        </div>
        """
    return html


# --- Tabs ---
tab_live, tab_insights, tab_architecture = st.tabs(
    ["Live Demo", "Pipeline Insights", "Architecture"]
)

# ========================
# Tab 1: Live Demo
# ========================
with tab_live:
    st.header("Live Demo")
    st.markdown(
        "Scrape the freshest Spotify Play Store reviews and classify them live with Groq."
    )

    col1, col2 = st.columns(2)

    # --- Button 1: Live Demo ---
    with col1:
        if st.button("🚀 Live Demo: Classify 5 Fresh Reviews", use_container_width=True):
            status = st.empty()
            progress_bar = st.progress(0)
            cards_container = st.empty()
            results = []

            try:
                with st.spinner("Scraping the 5 most recent US Play Store reviews..."):
                    review_generator = run_live_demo(n=5)

                status.info("Scraping complete. Classifying with fast model...")

                for i, review in enumerate(review_generator, start=1):
                    progress = int((i / 5) * 100)
                    progress_bar.progress(progress)
                    status.info(f"Classifying review {i} of 5...")

                    results.append(review)
                    cards_container.markdown(
                        render_review_cards(results), unsafe_allow_html=True
                    )

                progress_bar.empty()
                status.success(f"Classified {len(results)} fresh reviews")

            except Exception as e:
                progress_bar.empty()
                status.error(f"Demo failed: {e}")

    # --- Button 2: Trigger Full Pipeline ---
    with col2:
        if st.button("⚙️ Trigger Full Pipeline", use_container_width=True):
            with st.spinner("Dispatching GitHub Actions workflow..."):
                try:
                    success = trigger_full_pipeline()
                    if success:
                        st.success("Full pipeline triggered — running in background")
                        st.markdown(
                            "[View live logs on GitHub Actions →](https://github.com/pbehuray/spotify-discovery-engine/actions)"
                        )
                    else:
                        st.error("Failed to trigger pipeline. Check your GitHub token.")
                except Exception as e:
                    st.error(f"Could not trigger pipeline: {e}")


# ========================
# Tab 2: Pipeline Insights
# ========================
with tab_insights:
    st.header("Pipeline Insights")

    try:
        insights = load_insights()
    except Exception as e:
        st.error(f"Failed to load insights.json: {e}")
        st.stop()

    # --- Metric cards ---
    total = insights.get("total_reviews", 0)
    discovery = insights.get("discovery_related", {})
    discovery_count = discovery.get("count", 0)
    discovery_pct = discovery.get("percent", 0)

    by_segment = insights.get("by_segment", {})
    dominant_segment = max(by_segment, key=by_segment.get) if by_segment else "N/A"
    dominant_segment_count = by_segment.get(dominant_segment, 0)

    by_frustration = insights.get("by_frustration_type", {})
    top_frustration = max(by_frustration, key=by_frustration.get) if by_frustration else "N/A"
    top_frustration_count = by_frustration.get(top_frustration, 0)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Reviews", f"{total}")
    c2.metric("Discovery-related", f"{discovery_count}", f"{discovery_pct}%")
    c3.metric("Dominant Segment", f"{dominant_segment}", f"{dominant_segment_count}")
    c4.metric("Top Frustration", f"{top_frustration}", f"{top_frustration_count}")

    st.divider()

    # --- Charts row 1 ---
    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader("Frustration Types")
        if by_frustration:
            df_frustration = pd.DataFrame(
                {
                    "Frustration Type": list(by_frustration.keys()),
                    "Count": list(by_frustration.values()),
                }
            ).sort_values("Count", ascending=True)
            fig = px.bar(
                df_frustration,
                x="Count",
                y="Frustration Type",
                orientation="h",
                color="Count",
                color_continuous_scale=["#181818", SPOTIFY_GREEN],
                template="plotly_dark",
            )
            fig.update_layout(
                paper_bgcolor=DARK_BG,
                plot_bgcolor=DARK_BG,
                font_color="#ffffff",
                margin=dict(l=20, r=20, t=20, b=20),
            )
            st.plotly_chart(fig, use_container_width=True)

    with col_b:
        st.subheader("Segment Distribution")
        if by_segment:
            df_segment = pd.DataFrame(
                {
                    "Segment": list(by_segment.keys()),
                    "Count": list(by_segment.values()),
                }
            ).sort_values("Count", ascending=False)
            fig = px.bar(
                df_segment,
                x="Segment",
                y="Count",
                color="Count",
                color_continuous_scale=["#181818", SPOTIFY_GREEN],
                template="plotly_dark",
            )
            fig.update_layout(
                paper_bgcolor=DARK_BG,
                plot_bgcolor=DARK_BG,
                font_color="#ffffff",
                margin=dict(l=20, r=20, t=20, b=20),
            )
            st.plotly_chart(fig, use_container_width=True)

    # --- Heatmap row ---
    st.subheader("Segment × Frustration Crosstab")
    crosstab = insights.get("segment_x_frustration_crosstab", {})
    if crosstab:
        segments = list(crosstab.keys())
        frustrations = sorted(
            set(
                f for seg_values in crosstab.values() for f in seg_values.keys()
            )
        )
        heatmap_data = []
        for seg in segments:
            row = [seg]
            for f in frustrations:
                val = crosstab.get(seg, {}).get(f, 0)
                row.append(val)
            heatmap_data.append(row)

        df_heatmap = pd.DataFrame(heatmap_data, columns=["Segment"] + frustrations)
        df_heatmap = df_heatmap.set_index("Segment")

        fig = px.imshow(
            df_heatmap,
            color_continuous_scale=["#181818", SPOTIFY_GREEN],
            template="plotly_dark",
            aspect="auto",
            text_auto=True,
        )
        fig.update_layout(
            paper_bgcolor=DARK_BG,
            plot_bgcolor=DARK_BG,
            font_color="#ffffff",
            xaxis_title="Frustration Type",
            yaxis_title="Segment",
        )
        st.plotly_chart(fig, use_container_width=True)

        st.caption(
            f"Highlight: **{dominant_segment}** + **{top_frustration}** = {crosstab.get(dominant_segment, {}).get(top_frustration, 0)} reviews"
        )

    # --- Root causes & unmet needs ---
    col_c, col_d = st.columns(2)

    with col_c:
        st.subheader("Top Root Causes")
        root_causes = insights.get("top_root_causes", {})
        if root_causes:
            df_root = pd.DataFrame(
                {
                    "Root Cause": list(root_causes.keys())[:10],
                    "Count": list(root_causes.values())[:10],
                }
            )
            fig = px.bar(
                df_root,
                x="Count",
                y="Root Cause",
                orientation="h",
                color="Count",
                color_continuous_scale=["#181818", SPOTIFY_GREEN],
                template="plotly_dark",
            )
            fig.update_layout(
                paper_bgcolor=DARK_BG,
                plot_bgcolor=DARK_BG,
                font_color="#ffffff",
                margin=dict(l=20, r=20, t=20, b=20),
            )
            st.plotly_chart(fig, use_container_width=True)

    with col_d:
        st.subheader("Top Unmet Needs")
        unmet_needs = insights.get("top_unmet_needs", {})
        if unmet_needs:
            df_needs = pd.DataFrame(
                {
                    "Unmet Need": list(unmet_needs.keys())[:10],
                    "Count": list(unmet_needs.values())[:10],
                }
            )
            fig = px.bar(
                df_needs,
                x="Count",
                y="Unmet Need",
                orientation="h",
                color="Count",
                color_continuous_scale=["#181818", SPOTIFY_GREEN],
                template="plotly_dark",
            )
            fig.update_layout(
                paper_bgcolor=DARK_BG,
                plot_bgcolor=DARK_BG,
                font_color="#ffffff",
                margin=dict(l=20, r=20, t=20, b=20),
            )
            st.plotly_chart(fig, use_container_width=True)

    # --- Source breakdown ---
    st.subheader("Review Source Breakdown")
    by_source = insights.get("by_source", {})
    if by_source:
        df_source = pd.DataFrame(
            {
                "Source": list(by_source.keys()),
                "Count": list(by_source.values()),
            }
        )
        fig = px.pie(
            df_source,
            names="Source",
            values="Count",
            color="Source",
            color_discrete_sequence=["#1DB954", "#1ed760", "#2a2a2a", "#333333", "#444444"],
            template="plotly_dark",
        )
        fig.update_layout(
            paper_bgcolor=DARK_BG,
            plot_bgcolor=DARK_BG,
            font_color="#ffffff",
            margin=dict(l=20, r=20, t=20, b=20),
        )
        st.plotly_chart(fig, use_container_width=True)


# ========================
# Tab 3: Architecture
# ========================
with tab_architecture:
    st.header("Architecture")

    # --- Graphviz pipeline diagram ---
    dot = Digraph(
        format="png",
        graph_attr={"bgcolor": "#121212", "rankdir": "LR", "splines": "ortho"},
        node_attr={"shape": "box", "style": "rounded,filled", "fontcolor": "#ffffff", "fontsize": "12"},
        edge_attr={"color": "#1DB954", "fontcolor": "#B3B3B3", "fontsize": "10"},
    )

    dot.node("play", "Play Store", fillcolor="#1DB954")
    dot.node("app", "App Store", fillcolor="#333333")
    dot.node("reddit", "Reddit", fillcolor="#333333")
    dot.node("forum", "Forum", fillcolor="#333333")
    dot.node("social", "Social", fillcolor="#333333")
    dot.node("scraper", "Scraper", fillcolor="#2a2a2a")
    dot.node("paste", "Paste Importer", fillcolor="#2a2a2a")
    dot.node("supabase", "Supabase", fillcolor="#2a2a2a")
    dot.node("classifier", "Groq Classifier\nllama-3.3-70b-versatile", fillcolor="#2a2a2a")
    dot.node("aggregator", "Aggregator", fillcolor="#2a2a2a")
    dot.node("insights", "insights.json", fillcolor="#333333")
    dot.node("actions", "GitHub Actions\ncron 04:30 UTC", fillcolor="#1DB954")

    dot.edge("play", "scraper")
    dot.edge("app", "paste")
    dot.edge("reddit", "paste")
    dot.edge("forum", "paste")
    dot.edge("social", "paste")
    dot.edge("scraper", "supabase", label="raw_reviews")
    dot.edge("paste", "supabase", label="raw_reviews")
    dot.edge("supabase", "classifier", label="classify")
    dot.edge("classifier", "supabase", label="tagged_reviews")
    dot.edge("supabase", "aggregator", label="query")
    dot.edge("aggregator", "insights", label="generate")
    dot.edge("insights", "actions", label="commit")

    st.graphviz_chart(dot)

    # --- Pipeline stats ---
    st.subheader("Pipeline Stats")
    stats_col1, stats_col2, stats_col3, stats_col4 = st.columns(4)
    stats_col1.metric("Reviews", "456")
    stats_col2.metric("Sources", "6")
    stats_col3.metric("Classification Fields", "7")
    stats_col4.metric("Classifier", "llama-3.3-70b-versatile")

    # --- Link buttons ---
    st.subheader("Links")
    link_col1, link_col2 = st.columns(2)
    with link_col1:
        st.markdown(
            "<a href='https://github.com/pbehuray/spotify-discovery-engine' target='_blank'>"
            "<button style='background-color:#1DB954;color:#fff;border:none;border-radius:500px;"
            "padding:0.75rem 2rem;font-weight:700;width:100%;'>🗂️ GitHub Repo</button></a>",
            unsafe_allow_html=True,
        )
    with link_col2:
        st.markdown(
            "<a href='https://github.com/pbehuray/spotify-discovery-engine' target='_blank'>"
            "<button style='background-color:#1DB954;color:#fff;border:none;border-radius:500px;"
            "padding:0.75rem 2rem;font-weight:700;width:100%;'>🚀 Prototype</button></a>",
            unsafe_allow_html=True,
        )
