"""EPR regulation library."""

import streamlit as st
from uusio.frontend import api_client

COUNTRIES = ["EU", "FI", "SE", "NO", "DK", "DE", "FR", "NL", "BE", "PL", "AT", "ES", "IT"]
CATEGORIES = ["Packaging", "Electronics", "Batteries", "Textiles", "Tyres", "Vehicles", "Pharmaceuticals", "Other"]

FLAGS = {
    "FI": "\U0001f1eb\U0001f1ee", "SE": "\U0001f1f8\U0001f1ea",
    "NO": "\U0001f1f3\U0001f1f4", "DK": "\U0001f1e9\U0001f1f0",
    "DE": "\U0001f1e9\U0001f1ea", "FR": "\U0001f1eb\U0001f1f7",
    "NL": "\U0001f1f3\U0001f1f1", "BE": "\U0001f1e7\U0001f1ea",
    "PL": "\U0001f1f5\U0001f1f1", "AT": "\U0001f1e6\U0001f1f9",
    "ES": "\U0001f1ea\U0001f1f8", "IT": "\U0001f1ee\U0001f1f9",
    "EU": "\U0001f1ea\U0001f1fa",
}


def render() -> None:
    st.title("\U0001f4d6 Regulation Library")
    st.caption("EPR legislation and requirements by country")

    is_admin = st.session_state.get("is_admin", False)

    col1, col2, col3 = st.columns([1, 1, 2])
    country_filter = col1.selectbox("Country", ["All"] + COUNTRIES)
    cat_filter = col2.selectbox("Category", ["All"] + CATEGORIES)
    search = col3.text_input("Search", placeholder="Keyword...")

    country_code = None if country_filter == "All" else country_filter
    category = None if cat_filter == "All" else cat_filter

    try:
        entries = api_client.list_regulations(country_code=country_code, category=category, search=search or None)
    except Exception as e:
        st.error(str(e))
        return

    st.caption(f"{len(entries)} result(s)")
    st.divider()

    if not entries:
        st.info("No results. Try adjusting the filters.")
    else:
        for entry in entries:
            flag = FLAGS.get(entry["country_code"].upper(), "\U0001f310")
            with st.expander(f"{flag} **{entry['country_code']}** | {entry['category']} — {entry['title']}"):
                col_a, col_b = st.columns([3, 1])
                with col_a:
                    st.markdown(entry["summary"])
                    if entry.get("full_text"):
                        with st.expander("Read full text"):
                            st.markdown(entry["full_text"])
                with col_b:
                    if entry.get("effective_date"):
                        st.metric("Effective", entry["effective_date"])
                    if entry.get("tags"):
                        for tag in entry["tags"]:
                            st.markdown(f"`{tag}`")
                    if entry.get("source_url"):
                        st.markdown(f"[Source ↗]({entry['source_url']})")
                if is_admin:
                    ea, eb = st.columns(2)
                    with ea:
                        if st.button("Delete", key=f"del_{entry['id']}"):
                            api_client.delete_regulation(entry["id"])
                            st.rerun()
                    with eb:
                        if st.button("Archive", key=f"arch_{entry['id']}"):
                            api_client.update_regulation(entry["id"], {"is_active": False})
                            st.rerun()

    if is_admin:
        st.divider()
        with st.expander("➕ Add new regulation"):
            with st.form("new_regulation"):
                rc1, rc2 = st.columns(2)
                country = rc1.selectbox("Country", COUNTRIES, key="reg_country")
                category_new = rc2.selectbox("Category", CATEGORIES, key="reg_cat")
                title = st.text_input("Title")
                summary = st.text_area("Summary")
                full_text = st.text_area("Full text (optional)")
                eff_date = st.date_input("Effective date (optional)", value=None)
                source_url = st.text_input("Source URL (optional)")
                tags_raw = st.text_input("Tags (comma-separated)", placeholder="PPWR, SUP, take-back")
                submitted = st.form_submit_button("Save")

            if submitted:
                if not title or not summary:
                    st.error("Title and summary are required.")
                else:
                    tags = [t.strip() for t in tags_raw.split(",") if t.strip()] if tags_raw else []
                    api_client.create_regulation({"country_code": country, "category": category_new,
                                                  "title": title, "summary": summary,
                                                  "full_text": full_text or None,
                                                  "effective_date": eff_date.isoformat() if eff_date else None,
                                                  "source_url": source_url or None, "tags": tags})
                    st.success("Regulation added.")
                    st.rerun()
