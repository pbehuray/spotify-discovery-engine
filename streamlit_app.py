"""
Spotify Discovery Engine — Streamlit Frontend
Phase 5: Live demo dashboard
"""

import streamlit as st
from streamlit.backend import run_live_demo, trigger_full_pipeline

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

            status.info("Scraping the 5 most recent Play Store reviews...")

            try:
                for i, review in enumerate(run_live_demo(n=5), start=1):
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
# Tab 2: Pipeline Insights (placeholder)
# ========================
with tab_insights:
    st.header("Pipeline Insights")
    st.info("Insights dashboard coming soon. Load `insights.json` here.")


# ========================
# Tab 3: Architecture (placeholder)
# ========================
with tab_architecture:
    st.header("Architecture")
    st.info("Architecture diagram and pipeline overview coming soon.")
