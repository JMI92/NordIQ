"""EPR regulation library — visible to all users, admin can edit."""

import streamlit as st

from uusio.frontend import api_client

COUNTRIES = ["EU", "FI", "SE", "NO", "DK", "DE", "FR", "NL", "BE", "PL", "AT", "ES", "IT"]
CATEGORIES = ["Packaging", "Electronics", "Batteries", "Textiles", "Tyres", "Vehicles", "Pharmaceuticals", "Other"]


def render() -> None:
    st.title("\U0001f4d6 Säännöskirjasto")
    st.caption("EPR-lainsäädäntö ja vaatimukset maittain")

    is_admin = st.session_state.get("is_admin", False)

    # ----- Filters -----
    col1, col2, col3 = st.columns([1, 1, 2])
    country_filter = col1.selectbox("Maa", ["Kaikki"] + COUNTRIES)
    cat_filter = col2.selectbox("Kategoria", ["Kaikki"] + CATEGORIES)
    search = col3.text_input("Hae", placeholder="Hakusana...")

    country_code = None if country_filter == "Kaikki" else country_filter
    category = None if cat_filter == "Kaikki" else cat_filter

    entries = api_client.list_regulations(
        country_code=country_code,
        category=category,
        search=search or None,
    )

    st.caption(f"{len(entries)} hakutulosta")
    st.divider()

    if not entries:
        st.info("Ei hakutuloksia.")
    else:
        for entry in entries:
            flag = _country_flag(entry["country_code"])
            with st.expander(f"{flag} **{entry['country_code']}** | {entry['category']} — {entry['title']}"):
                col_a, col_b = st.columns([3, 1])
                with col_a:
                    st.markdown(entry["summary"])
                    if entry.get("full_text"):
                        with st.expander("Lue koko teksti"):
                            st.markdown(entry["full_text"])
                with col_b:
                    if entry.get("effective_date"):
                        st.metric("Voimaanastuminen", entry["effective_date"])
                    if entry.get("tags"):
                        for tag in entry["tags"]:
                            st.markdown(f"`{tag}`")
                    if entry.get("source_url"):
                        st.markdown(f"[Lähde]({entry['source_url']})")

                if is_admin:
                    ea, eb = st.columns(2)
                    with ea:
                        if st.button("Poista", key=f"del_{entry['id']}"):
                            api_client.delete_regulation(entry["id"])
                            st.rerun()
                    with eb:
                        if st.button("Arkistoi", key=f"arch_{entry['id']}"):
                            api_client.update_regulation(entry["id"], {"is_active": False})
                            st.rerun()

    # ----- Add new entry (admin only) -----
    if is_admin:
        st.divider()
        with st.expander("➕ Lisää uusi sääntö"):
            with st.form("new_regulation"):
                rc1, rc2 = st.columns(2)
                country = rc1.selectbox("Maa", COUNTRIES, key="reg_country")
                category_new = rc2.selectbox("Kategoria", CATEGORIES, key="reg_cat")
                title = st.text_input("Otsikko")
                summary = st.text_area("Tiivistelmä")
                full_text = st.text_area("Koko teksti (valinnainen)")
                eff_date = st.date_input("Voimaanastuminen (valinnainen)", value=None)
                source_url = st.text_input("Lähde URL (valinnainen)")
                tags_raw = st.text_input("Tunnisteet pilkulla erotettuna", placeholder="PPWR, SUP, take-back")
                submitted = st.form_submit_button("Tallenna")

            if submitted:
                if not title or not summary:
                    st.error("Otsikko ja tiivistelmä ovat pakollisia.")
                else:
                    tags = [t.strip() for t in tags_raw.split(",") if t.strip()] if tags_raw else []
                    payload = {
                        "country_code": country,
                        "category": category_new,
                        "title": title,
                        "summary": summary,
                        "full_text": full_text or None,
                        "effective_date": eff_date.isoformat() if eff_date else None,
                        "source_url": source_url or None,
                        "tags": tags,
                    }
                    api_client.create_regulation(payload)
                    st.success("Sääntö lisätty.")
                    st.rerun()


def _country_flag(code: str) -> str:
    flags = {
        "FI": "\U0001f1eb\U0001f1ee", "SE": "\U0001f1f8\U0001f1ea",
        "NO": "\U0001f1f3\U0001f1f4", "DK": "\U0001f1e9\U0001f1f0",
        "DE": "\U0001f1e9\U0001f1ea", "FR": "\U0001f1eb\U0001f1f7",
        "NL": "\U0001f1f3\U0001f1f1", "BE": "\U0001f1e7\U0001f1ea",
        "PL": "\U0001f1f5\U0001f1f1", "AT": "\U0001f1e6\U0001f1f9",
        "ES": "\U0001f1ea\U0001f1f8", "IT": "\U0001f1ee\U0001f1f9",
        "EU": "\U0001f1ea\U0001f1fa",
    }
    return flags.get(code.upper(), "\U0001f310")
