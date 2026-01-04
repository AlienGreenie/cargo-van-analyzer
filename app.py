import streamlit as st
import requests
import math
from bs4 import BeautifulSoup

# ==============================
# 🛣️ Google Maps Route + Distance + Toll Info
# ==============================
@st.cache_data(ttl=600)
def get_google_route(origin, destination):
    url = (
        f"https://maps.googleapis.com/maps/api/directions/json?"
        f"origin={origin}&destination={destination}&key={st.secrets['GOOGLE_API_KEY']}&mode=driving"
    )
    try:
        r = requests.get(url, timeout=10).json()
        if r['status'] != 'OK':
            return None, None
        distance_meters = r['routes'][0]['legs'][0]['distance']['value']
        distance_miles = distance_meters * 0.000621371

        # Simple toll detection using steps (Google Maps does not return toll info reliably for free API)
        steps = r['routes'][0]['legs'][0]['steps']
        toll_present = any("toll" in step.get("html_instructions", "").lower() for step in steps)

        return distance_miles, toll_present
    except:
        return None, None

# ==============================
# 📊 DAT Ratio Scrape
# ==============================
@st.cache_data(ttl=1800)
def get_live_dat_ratio():
    try:
        url = "https://www.dat.com/industry-trends/trendlines/van"
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(r.text, "html.parser")
        ratio = soup.find("div", class_="ratio-value")
        return float(ratio.text.strip())
    except:
        return 3.0

# ==============================
# UI
# ==============================
st.set_page_config("Cargo Van Web Analyzer", layout="wide")
st.title("🚐 Cargo Van Web Analyzer")
st.caption("Google Maps • DAT Market • Dashboard Web")

# ------------------------------
# Tabs layout
# ------------------------------
tabs = st.tabs(["Analyze Load", "Load History"])

# ------------------------------
# Tab 1: Analyze Load
# ------------------------------
with tabs[0]:
    col1, col2 = st.columns(2)

    # Main Inputs
    with col1:
        origin = st.text_input("Origin (ZIP / City, State)", "27703, NC")
        destination = st.text_input("Destination (ZIP / City, State)", "07202, NJ")
        deadhead = st.number_input("Deadhead miles (empty return)", value=0)

    with col2:
        broker_pay = st.number_input("Broker Pay ($)", min_value=0.0)
        live_dat = get_live_dat_ratio()
        dat_ratio = st.number_input(f"DAT Ratio (Live {live_dat:.2f})", value=live_dat)

    # Sidebar / Costs
    with st.sidebar:
        st.header("⚙️ Van Setup & Costs")
        fuel_type = st.selectbox("Fuel Type", ["Gasoline", "Diesel"])
        mpg = st.number_input("MPG", value=14.0 if fuel_type=="Gasoline" else 15.5)
        fuel_price = st.number_input(f"Fuel Price ($/gal)", value=3.60 if fuel_type=="Gasoline" else 4.00)
        miles_day = st.number_input("Miles per day", value=500)
        insurance_month = st.number_input("Insurance / month ($)", value=1200.0)
        otr_days = st.number_input("OTR days / month", value=21)

        st.divider()
        st.subheader("⚙️ Maintenance")
        maint_cpm = st.number_input("Maintenance ($ per mile)", value=0.03, step=0.005)

        st.divider()
        st.subheader("⚙️ Tolls")
        tolls_manual = st.number_input("Tolls ($)", value=0.0)

        st.divider()
        if st.button("🔄 Refresh APIs Cache"):
            st.cache_data.clear()

    # Calculate
    if st.button("🔥 ANALYZE LOAD"):
        miles, toll_present = get_google_route(origin, destination)
        miles += deadhead
        tolls = tolls_manual

        if not miles:
            st.error("Route calculation failed. Check addresses.")
        else:
            market_adj = 1.0
            if dat_ratio < 2: market_adj = 1.2
            elif dat_ratio < 2.5: market_adj = 1.1

            days_trip = math.ceil(miles / miles_day)
            fuel_cost = (miles / mpg) * fuel_price
            maint_cost = miles * maint_cpm
            insurance_cost = (insurance_month / otr_days) * days_trip

            total_cost = (fuel_cost + maint_cost + insurance_cost + tolls) * market_adj
            profit = broker_pay - total_cost
            margin = (profit / total_cost) * 100 if total_cost else 0
            cpm = total_cost / miles if miles else 0
            rpm = broker_pay / miles if miles else 0

            st.session_state["current_load"] = {
                "miles": miles,
                "tolls": tolls,
                "toll_present": toll_present,
                "days_trip": days_trip,
                "total_cost": total_cost,
                "profit": profit,
                "margin": margin,
                "fuel_cost": fuel_cost,
                "maint_cost": maint_cost,
                "insurance_cost": insurance_cost,
                "cpm": cpm,
                "rpm": rpm
            }

    # Results Dashboard
    if "current_load" in st.session_state:
        load = st.session_state["current_load"]
        st.subheader("📊 Analysis Results")
        r1, r2, r3, r4 = st.columns(4)
        r1.metric("Net Profit", f"${load['profit']:.2f}")
        r2.metric("Profit Margin", f"{load['margin']:.1f}%")
        r3.metric("Real Cost", f"${load['total_cost']:.2f}")
        r4.metric("Target Rate (40%)", f"${load['total_cost']*1.4:.2f}")

        r5, r6, r7, r8 = st.columns(4)
        r5.metric("Total Miles", f"{load['miles']:.0f}")
        r6.metric("Days on Trip", load['days_trip'])
        r7.metric("Tolls Present", "Yes ✅" if load['toll_present'] else "No ❌")
        r8.metric("CPM", f"${load['cpm']:.2f} / mile")
        st.metric("RPM", f"${load['rpm']:.2f} / mile")

        st.subheader("💰 Cost Breakdown")
        c1, c2, c3, c4 = st.columns(4)
        c1.write(f"Fuel: ${load['fuel_cost']:.2f}")
        c2.write(f"Maintenance: ${load['maint_cost']:.2f}")
        c3.write(f"Insurance: ${load['insurance_cost']:.2f}")
        c4.write(f"Tolls: ${load['tolls']:.2f}")

        # Google Maps Interactive Embed
        map_url = f"https://www.google.com/maps/embed/v1/directions?key={st.secrets['GOOGLE_API_KEY']}&origin={origin}&destination={destination}&mode=driving"
        st.subheader("🗺 Route Map (Google Maps)")
        st.components.v1.iframe(map_url, width=800, height=500)

# ------------------------------
# Tab 2: Load History Placeholder
# ------------------------------
with tabs[1]:
    st.subheader("📋 Load History")
    st.info("This will store previous analyzed loads. Feature coming soon!")
