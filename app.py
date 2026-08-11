import streamlit as st
import pandas as pd
import requests

st.set_page_config(page_title="ระบบข้อมูลเกษตรจาก API", layout="wide")
st.title("ระบบข้อมูลเกษตรจาก API (Live Agri-Data)")
st.caption("ดึงข้อมูลจริงแบบสดจากอินเทอร์เน็ต แล้วแสดงผลโต้ตอบได้")

# ส่ง User-Agent แบบเบราว์เซอร์ ช่วยให้บาง API ไม่บล็อกว่าเป็นบอท
HEADERS = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/124.0 Safari/537.36"),
           "Accept": "application/json"}

# หมายเหตุ: ชื่อคอลัมน์ห้ามมีจุด "." หรือวงเล็บ เพราะกราฟของ Streamlit (Vega-Lite)
# จะตีความจุดเป็นตัวเข้าถึงฟิลด์ย่อย ทำให้วาดค่าไม่ออก — หน่วยจึงไปไว้ที่ caption/label แทน

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

# ราคาสำรอง (snapshot ธ.ค. 2567) ใช้แสดงเมื่อเซิร์ฟเวอร์เข้า data.go.th ไม่ได้
ราคาสำรอง = pd.DataFrame({
    "สินค้า": ["ทุเรียนหมอนทองคละ", "ยางแผ่นดิบชั้น 3", "เงาะโรงเรียนคละ",
              "กล้วยหอมทองขนาดคละ", "สับปะรดโรงงาน", "มันสำปะหลังคละ"],
    "ราคา": [135.0, 76.4, 40.2, 20.0, 12.5, 1.3],
})

@st.cache_data(ttl=86400)
def _ดึงราคาดิบ():
    URL = "https://data.go.th/api/3/action/datastore_search"
    RESOURCE_ID = "38b840af-f119-4bea-9208-66188da5cc1b"
    resp = requests.get(URL, params={"resource_id": RESOURCE_ID, "limit": 5000},
                        headers=HEADERS, timeout=30)
    resp.raise_for_status()
    recs = resp.json()["result"]["records"]   # ถ้าตอบไม่ใช่ JSON จะ error แล้วไปใช้ค่าสำรอง
    ราคา = pd.DataFrame(recs).rename(columns={"เกษตรสำคัญบึงกาฬ": "สินค้า", "ค่า": "ราคา"})
    ราคา["ราคา"] = pd.to_numeric(ราคา["ราคา"], errors="coerce")
    return ราคา

def ดึงราคาเกษตร():
    # st.cache_data ไม่เก็บผลตอน error ดังนั้นถ้าพลาดครั้งนี้ ครั้งหน้าจะลองใหม่เอง
    try:
        return _ดึงราคาดิบ(), True
    except Exception:
        return None, False

# ---------- โมเดลแนะนำการรดน้ำ (Lab 5) ----------
# ข้อมูลชุดเดียวกับ course-labs/Lab05/lab05-water.csv (12 แถว)
ข้อมูลรดน้ำ = """moisture,temp,rain,water
25,33,0,1
30,32,0,1
60,28,10,0
70,27,15,0
20,35,0,1
55,30,2,1
65,29,12,0
40,31,1,1
75,26,20,0
35,34,0,1
50,30,8,0
28,33,0,1
"""

@st.cache_resource          # เทรนครั้งเดียวแล้วเก็บไว้ ไม่เทรนใหม่ทุกครั้งที่ผู้ใช้ขยับสไลเดอร์
def สร้างโมเดลรดน้ำ():
    from io import StringIO
    from sklearn.ensemble import RandomForestClassifier
    d = pd.read_csv(StringIO(ข้อมูลรดน้ำ))
    m = RandomForestClassifier(n_estimators=100, random_state=42)
    m.fit(d[["moisture", "temp", "rain"]], d["water"])
    return m, d

แท็บอากาศ, แท็บน้ำ, แท็บราคา, แท็บรดน้ำ = st.tabs(
    ["สภาพอากาศ", "ระดับน้ำแม่น้ำ", "ราคาสินค้าเกษตร", "แนะนำการรดน้ำ"])

# ---------- แท็บ 1: สภาพอากาศ (Open-Meteo) ----------
with แท็บอากาศ:
    st.subheader("พยากรณ์อากาศรายวันของสวน")
    c1, c2, c3 = st.columns(3)
    lat = c1.number_input("ละติจูด", value=18.90)
    lon = c2.number_input("ลองจิจูด", value=99.01)
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

# ---------- แท็บ 2: ระดับน้ำแม่น้ำ (flood API) ----------
with แท็บน้ำ:
    st.subheader("ปริมาณการไหลของแม่น้ำ (เตือนภัยน้ำท่วม)")
    c1, c2 = st.columns(2)
    lat2 = c1.number_input("ละติจูด (จุดใกล้แม่น้ำ)", value=18.90, key="lat_river")
    lon2 = c2.number_input("ลองจิจูด (จุดใกล้แม่น้ำ)", value=99.01, key="lon_river")
    try:
        r = ดึงระดับน้ำ(lat2, lon2)
        st.write("ปริมาณการไหล (ลูกบาศก์เมตร/วินาที)")
        st.line_chart(r.set_index("วันที่")["ปริมาณน้ำ"])
        st.info("ยิ่งค่าสูง = น้ำในแม่น้ำยิ่งมาก/เสี่ยงท่วม (เป็นปริมาณการไหล ไม่ใช่ระดับเป็นเมตร)")
        with st.expander("ดูข้อมูลดิบทั้งหมด"):
            st.dataframe(r)
    except Exception as e:
        st.error(f"ดึงระดับน้ำไม่สำเร็จ ลองใหม่อีกครั้ง (สาเหตุ: {e})")

# ---------- แท็บ 3: ราคาสินค้าเกษตร (data.go.th) ----------
with แท็บราคา:
    st.subheader("ราคาสินค้าเกษตรจริง (ข้อมูลเปิดภาครัฐ)")
    ราคา, สด = ดึงราคาเกษตร()
    if not สด:
        st.warning("ตอนนี้เซิร์ฟเวอร์เข้า data.go.th ไม่ได้ "
                   "(มักถูกบล็อกจาก IP ดาต้าเซ็นเตอร์) — แสดงราคาสำรองล่าสุด ธ.ค. 2567 แทน")
        st.write("ราคาล่าสุด (บาท/กก.)")
        st.bar_chart(ราคาสำรอง.set_index("สินค้า")["ราคา"])
        st.dataframe(ราคาสำรอง, hide_index=True)
    else:
        ปีล่าสุด = int(ราคา["ปี"].max())
        สินค้าทั้งหมด = sorted(ราคา["สินค้า"].dropna().unique())
        ค่าเริ่ม = [s for s in ["ทุเรียนหมอนทองคละ", "เงาะโรงเรียนคละ", "ยางแผ่นดิบชั้น 3"]
                   if s in สินค้าทั้งหมด]
        เลือก = st.multiselect("เลือกสินค้าที่จะดู", สินค้าทั้งหมด, default=ค่าเริ่ม)
        st.caption(f"ข้อมูลล่าสุดปี พ.ศ. {ปีล่าสุด} — สถิติทางการรายเดือน (จ.บึงกาฬ) หน่วย บาท/กก.")
        เดือนเรียง = ["ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.",
                     "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."]
        if เลือก:
            ปีนี้ = ราคา[(ราคา["ปี"] == ปีล่าสุด) & (ราคา["สินค้า"].isin(เลือก))].copy()
            ปีนี้["เดือน"] = pd.Categorical(ปีนี้["เดือน"], categories=เดือนเรียง, ordered=True)
            ตาราง = ปีนี้.pivot_table(index="เดือน", columns="สินค้า",
                                     values="ราคา", observed=False)
            ตาราง = ตาราง.sort_index()
            ตาราง.index = ตาราง.index.astype(str)   # เลี่ยง categorical index ที่กราฟไม่ยอมวาด
            st.line_chart(ตาราง)
            เดือนล่าสุด = ตาราง.dropna(how="all").index[-1]
            st.write(f"ราคาเดือนล่าสุด ({เดือนล่าสุด} {ปีล่าสุด}) หน่วย บาท/กก.")
            แถวล่าสุด = ตาราง.loc[[เดือนล่าสุด]].T
            แถวล่าสุด.columns = ["ราคา"]
            st.dataframe(แถวล่าสุด)
        else:
            st.warning("เลือกสินค้าอย่างน้อย 1 อย่าง")

# ---------- แท็บ 4: แนะนำการรดน้ำ (โมเดล ML จาก Lab 5) ----------
with แท็บรดน้ำ:
    st.subheader("ระบบแนะนำการรดน้ำ (Machine Learning)")
    st.caption("โมเดล Random Forest เรียนจากข้อมูลเซนเซอร์ 12 แถว แล้วตอบว่าวันนี้ควรรดน้ำหรือไม่")

    โมเดล, ตารางสอน = สร้างโมเดลรดน้ำ()

    c1, c2 = st.columns(2)
    ความชื้นดิน = c1.slider("ความชื้นดิน (%)", 0, 100, 40)
    อุณหภูมิ = c2.slider("อุณหภูมิ (°C)", 15, 40, 30)

    ใช้ฝนจริง = st.checkbox("ดึงฝนพยากรณ์จริงมาใช้ (จากพิกัดในแท็บสภาพอากาศ)", value=True)
    if ใช้ฝนจริง:
        try:
            ฝน = float(ดึงอากาศ(lat, lon, 3)["ฝน"].iloc[:2].sum())
            st.caption(f"ฝนพยากรณ์ 2 วันข้างหน้าที่พิกัด {lat}, {lon} = {ฝน:.1f} มม.")
        except Exception:
            ฝน = 0.0
            st.caption("ดึงพยากรณ์ไม่สำเร็จ ใช้ค่า 0 มม. แทน")
    else:
        ฝน = float(st.slider("ฝนพยากรณ์ (มม.)", 0, 50, 0))

    x = pd.DataFrame([[ความชื้นดิน, อุณหภูมิ, ฝน]],
                     columns=["moisture", "temp", "rain"])
    ผล = int(โมเดล.predict(x)[0])
    ความมั่นใจ = float(โมเดล.predict_proba(x)[0][ผล])

    if ผล == 1:
        st.success(f"### ควรรดน้ำ\nความมั่นใจของโมเดล {ความมั่นใจ:.0%}")
    else:
        st.info(f"### ไม่ต้องรดน้ำ\nดินชื้นพอหรือฝนกำลังจะตก — ความมั่นใจ {ความมั่นใจ:.0%}")

    with st.expander("ดูข้อมูลที่ใช้สอนโมเดล (12 แถว)"):
        st.dataframe(ตารางสอน, hide_index=True)
        st.caption("water: 1 = ควรรดน้ำ, 0 = ไม่ต้องรด — "
                   "ข้อมูลชุดเดียวกับ course-labs/Lab05/lab05-water.csv")
