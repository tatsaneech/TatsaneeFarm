import streamlit as st
import pandas as pd
import requests

st.set_page_config(page_title="ระบบข้อมูลสวนลำไย จ.เชียงใหม่", layout="wide")
st.title("ระบบข้อมูลสวนลำไย จ.เชียงใหม่ (Live Agri-Data)")
st.caption("เวอร์ชันปรับตามพื้นที่: พิกัดเริ่มต้น = เชียงใหม่ · ราคา = ลำไย (พืชหลักของภาคเหนือ)")

HEADERS = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/124.0 Safari/537.36"),
           "Accept": "application/json"}

# พิกัดเริ่มต้น = ตัวเมืองเชียงใหม่ (เปลี่ยนเป็นพิกัดสวนของคุณได้)
CM_LAT, CM_LON = 18.79, 98.98
เกรดเรียง = ["AA", "A", "B", "C"]

@st.cache_data(ttl=1800)
def ดึงอากาศ(lat, lon, days):
    url = (f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
           f"&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,"
           f"relative_humidity_2m_mean,wind_speed_10m_max,shortwave_radiation_sum"
           f"&timezone=Asia/Bangkok&forecast_days={days}")
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    w = pd.DataFrame(resp.json()["daily"])
    w.columns = ["วันที่", "สูงสุด", "ต่ำสุด", "ฝน", "ความชื้น", "ลม", "แสง"]
    return w

@st.cache_data(ttl=1800)
def ดึงระดับน้ำ(lat, lon):
    url = (f"https://flood-api.open-meteo.com/v1/flood?latitude={lat}&longitude={lon}"
           f"&daily=river_discharge&forecast_days=30")
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    r = pd.DataFrame(resp.json()["daily"])
    r.columns = ["วันที่", "ปริมาณน้ำ"]
    return r

# ราคาลำไยสำรอง (สดรูดร่วง ปี 2567) ใช้เมื่อเซิร์ฟเวอร์เข้า data.go.th ไม่ได้
ลำไยสำรอง = pd.DataFrame({"เกรด": เกรดเรียง, "ราคา": [31.17, 17.83, 9.83, 3.17]})

@st.cache_data(ttl=86400)
def _ดึงลำไยดิบ():
    URL = "https://data.go.th/api/3/action/datastore_search"
    RESOURCE_ID = "3dd78b27-a305-459a-8e93-27dc7b92a7b3"  # ราคาลำไย (แยกชนิด/เกรด รายปี)
    resp = requests.get(URL, params={"resource_id": RESOURCE_ID, "limit": 100},
                        headers=HEADERS, timeout=30)
    resp.raise_for_status()
    df = pd.DataFrame(resp.json()["result"]["records"])
    df["ชนิด"] = df["ชนิด"].str.strip()
    df["ราคา"] = pd.to_numeric(df["ราคา"], errors="coerce")
    df["ปี"] = pd.to_numeric(df["ปี"], errors="coerce").astype("Int64")
    return df

def ดึงราคาลำไย():
    try:
        return _ดึงลำไยดิบ(), True
    except Exception:
        return None, False

แท็บอากาศ, แท็บน้ำ, แท็บราคา, แท็บราคาลำไย = st.tabs(
    ["สภาพอากาศ", "ระดับน้ำแม่น้ำ", "ราคาลำไย", "ราคาลำไย (แยกเกรด)"])

# ---------- แท็บ 1: สภาพอากาศ ----------
with แท็บอากาศ:
    st.subheader("พยากรณ์อากาศรายวันของสวน (เชียงใหม่)")
    c1, c2, c3 = st.columns(3)
    lat = c1.number_input("ละติจูด", value=CM_LAT)
    lon = c2.number_input("ลองจิจูด", value=CM_LON)
    วัน = c3.slider("จำนวนวันล่วงหน้า", 3, 16, 15)
    try:
        w = ดึงอากาศ(lat, lon, วัน)
        m1, m2, m3 = st.columns(3)
        m1.metric("อุณหภูมิสูงสุดพรุ่งนี้", f"{w['สูงสุด'].iloc[1]:.0f} °C")
        m2.metric("ฝนรวม (ช่วงที่ดู)", f"{w['ฝน'].sum():.0f} มม.")
        m3.metric("ความชื้นเฉลี่ย", f"{w['ความชื้น'].mean():.0f} %")
        st.write("อุณหภูมิสูงสุด/ต่ำสุด (°C)")
        st.line_chart(w.set_index("วันที่")[["สูงสุด", "ต่ำสุด"]])
        st.write("ปริมาณฝนรายวัน (มม.)")
        st.bar_chart(w.set_index("วันที่")["ฝน"])
        with st.expander("ดูข้อมูลดิบทั้งหมด (หน่วย: °C, มม., %, กม./ชม., MJ/m²)"):
            st.dataframe(w)
    except Exception as e:
        st.error(f"ดึงข้อมูลอากาศไม่สำเร็จ ลองใหม่อีกครั้ง (สาเหตุ: {e})")

# ---------- แท็บ 2: ระดับน้ำแม่น้ำ ----------
with แท็บน้ำ:
    st.subheader("ปริมาณการไหลของแม่น้ำปิง/ลำน้ำใกล้สวน (เตือนภัยน้ำท่วม)")
    c1, c2 = st.columns(2)
    lat2 = c1.number_input("ละติจูด (จุดใกล้แม่น้ำ)", value=CM_LAT, key="lat_river")
    lon2 = c2.number_input("ลองจิจูด (จุดใกล้แม่น้ำ)", value=CM_LON, key="lon_river")
    try:
        r = ดึงระดับน้ำ(lat2, lon2)
        st.write("ปริมาณการไหล (ลูกบาศก์เมตร/วินาที)")
        st.line_chart(r.set_index("วันที่")["ปริมาณน้ำ"])
        st.info("ยิ่งค่าสูง = น้ำในแม่น้ำยิ่งมาก/เสี่ยงท่วม (เป็นปริมาณการไหล ไม่ใช่ระดับเป็นเมตร)")
        with st.expander("ดูข้อมูลดิบทั้งหมด"):
            st.dataframe(r)
    except Exception as e:
        st.error(f"ดึงระดับน้ำไม่สำเร็จ ลองใหม่อีกครั้ง (สาเหตุ: {e})")

# ---------- แท็บ 3: ราคาลำไย (แยกเกรด) ----------
with แท็บราคา:
    st.subheader("ราคาลำไยจริง แยกตามเกรด (ข้อมูลเปิดภาครัฐ)")
    df, สด = ดึงราคาลำไย()
    if not สด:
        st.warning("ตอนนี้เซิร์ฟเวอร์เข้า data.go.th ไม่ได้ "
                   "(มักถูกบล็อกจาก IP ดาต้าเซ็นเตอร์) — แสดงราคาสำรอง (สดรูดร่วง ปี 2567) แทน")
        st.write("ราคาตามเกรด (บาท/กก.)")
        st.bar_chart(ลำไยสำรอง.set_index("เกรด")["ราคา"])
        st.dataframe(ลำไยสำรอง, hide_index=True)
    else:
        ชนิด = st.radio("เลือกชนิดลำไย", sorted(df["ชนิด"].dropna().unique()), horizontal=True)
        เฉพาะ = df[df["ชนิด"] == ชนิด]
        ปีล่าสุด = int(เฉพาะ["ปี"].max())
        st.caption("ข้อมูลจาก data.go.th (สำนักงานเศรษฐกิจการเกษตร) หน่วย บาท/กก.")

        st.write(f"ราคาตามเกรด ปี {ปีล่าสุด}")
        แท่ง = (เฉพาะ[เฉพาะ["ปี"] == ปีล่าสุด]
                .set_index("เกรด")["ราคา"].reindex(เกรดเรียง))
        st.bar_chart(แท่ง)

        st.write("แนวโน้มราคาตามปี (แยกเกรด)")
        เส้น = เฉพาะ.pivot_table(index="ปี", columns="เกรด",
                                values="ราคา", observed=False)
        เส้น = เส้น.reindex(columns=[g for g in เกรดเรียง if g in เส้น.columns])
        เส้น.index = เส้น.index.astype(str)
        st.line_chart(เส้น)

        st.info("เกรดยิ่งดี (AA สูงสุด) ราคายิ่งสูง — เจ้าของสวนใช้วางแผนคัดเกรด/ช่วงเก็บเกี่ยวได้")

# ---------- แท็บ 4: ราคาลำไย (แยกเกรด) ----------
with แท็บราคาลำไย:
    st.subheader("ราคาลำไยจริง แยกตามเกรด (ข้อมูลเปิดภาครัฐ)")
    df, สด = ดึงราคาลำไย()
    if not สด:
        st.warning("ตอนนี้เซิร์ฟเวอร์เข้า data.go.th ไม่ได้ "
                   "(มักถูกบล็อกจาก IP ดาต้าเซ็นเตอร์) — แสดงราคาสำรอง (สดรูดร่วง ปี 2567) แทน")
        st.write("ราคาตามเกรด (บาท/กก.)")
        st.bar_chart(ลำไยสำรอง.set_index("เกรด")["ราคา"])
        st.dataframe(ลำไยสำรอง, hide_index=True)
    else:
        ชนิด = st.radio("เลือกชนิดลำไย", sorted(df["ชนิด"].dropna().unique()), horizontal=True)
        เฉพาะ = df[df["ชนิด"] == ชนิด]
        ปีล่าสุด = int(เฉพาะ["ปี"].max())
        st.caption("ข้อมูลจาก data.go.th (สำนักงานเศรษฐกิจการเกษตร) หน่วย บาท/กก.")

        st.write(f"ราคาตามเกรด ปี {ปีล่าสุด}")
        แท่ง = (เฉพาะ[เฉพาะ["ปี"] == ปีล่าสุด]
                .set_index("เกรด")["ราคา"].reindex(เกรดเรียง))
        st.bar_chart(แท่ง)

        st.write("แนวโน้มราคาตามปี (แยกเกรด)")
        เส้น = เฉพาะ.pivot_table(index="ปี", columns="เกรด",
                                values="ราคา", observed=False)
        เส้น = เส้น.reindex(columns=[g for g in เกรดเรียง if g in เส้น.columns])
        เส้น.index = เส้น.index.astype(str)
        st.line_chart(เส้น)

        st.info("เกรดยิ่งดี (AA สูงสุด) ราคายิ่งสูง — เจ้าของสวนใช้วางแผนคัดเกรด/ช่วงเก็บเกี่ยวได้")