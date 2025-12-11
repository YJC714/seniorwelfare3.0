
import streamlit as st
import pandas as pd
import datetime
import random
from io import BytesIO
from PIL import Image
from barcode import Code128
from barcode.writer import ImageWriter
import pydeck as pdk
from streamlit_javascript import st_javascript
import math
import venue
from venue import all_places
import plotly.express as px
# 長者 App 開頭加入
import json
from pathlib import Path

# ====================== 長者端 - 正確載入處方箋與個管師 ======================
DATA_DIR = Path("data")
PATIENTS_FILE = DATA_DIR / "patients.json"
RECORDS_FILE = DATA_DIR / "exercise_records.json"
PRESCRIPTION_FILE = DATA_DIR / "prescriptions.json"

# 目前測試用的長者病歷號（之後改成登入）
CURRENT_PATIENT_ID = "001"

def load_json(file):
    if file.exists():
        return json.loads(file.read_text(encoding="utf-8"))
    return {}

# 載入所有資料
patients_data = load_json(PATIENTS_FILE)
records_data = load_json(RECORDS_FILE)
prescriptions_all = load_json(PRESCRIPTION_FILE)

# 取得這位長者的完整資料
user = patients_data.get(CURRENT_PATIENT_ID, {
    "name": "王聖德",
    "total_points_auto": 0,
    "total_points_pending": 0,
    "total_points_approved": 0,
    "case_manager": "高曼玉"
})

# 設定姓名顯示
st.session_state.user_name = user.get("name", "長者")

# 關鍵：取得負責的個管師
case_manager_id = user.get("case_manager")  # 例如 "wang", "lily123", None

# 取得該個管師為這位長者開的處方（取最新一筆）
#prescription = None
#if case_manager_id and case_manager_id in prescriptions_all:
 #   patient_pres_list = prescriptions_all[case_manager_id].get(CURRENT_PATIENT_ID, [])
  #  if patient_pres_list:
   #     prescription = patient_pres_list[-1]  # 最新一筆
prescription = {
        "開立日期": "2025-12-9",
        "個管師": user.get("case_manager", "王小明") ,
        "處方內容": ["每天散步20分鐘\n坐在椅子上做起立訓練，一天20下\n每周至少參加1次社區活動或課程訓練"]
    }

# 如果沒有處方箋，就顯示預設訊息
if not prescription:
    prescription = {
        "開立日期": "尚未開立",
        "個管師": user.get("case_manager", "尚未指派") if user.get("case_manager") else "尚未指派",
        "處方內容": ["請聯繫您的個管師開立運動處方箋"]
    }
else:
    # 確保有這些欄位，避免 KeyError
    prescription.setdefault("處方內容", ["個管師指示運動項目"])
    prescription.setdefault("個管師", case_manager_id)



# ====================== 頁面設定 ======================
st.set_page_config(
    #page_title="長輩運動健康平台",
    page_icon="runner",
    layout="wide",
    #initial_sidebar_state="expanded"
    initial_sidebar_state="collapsed"
)

# ====================== 初始化 ======================
for key in ["records", "redeemed", "total_points", "user_name", "page"]:
    if key not in st.session_state:
        st.session_state[key] = {
            "records": [], "redeemed": [], "total_points": 0,
            "user_name": "王聖德", "page": "home"
        }[key]
taiwan_data = {
    '臺北市': ['中正區', '大安區', '信義區', '松山區', '中山區', '中西區', '大同區', '萬華區', '文山區', '南港區', '內湖區', '士林區', '北投區'],
    '新北市': ['板橋區', '新店區', '中和區', '永和區', '土城區', '三峽區', '樹林區', '鶯歌區', '三重區', '蘆洲區', '五股區', '泰山區', '林口區', '淡水區', '金山區', '萬里區', '汐止區', '瑞芳區', '平溪區', '雙溪區', '貢寮區', '新莊區', '坪林區', '烏來區', '深坑區', '石碇區', '三芝區', '石門區'],
    '桃園市': ['桃園區', '中壢區', '八德區', '平鎮區', '龍潭區', '楊梅區', '新屋區', '觀音區', '蘆竹區', '大溪區', '復興區', '大園區', '龜山區'],
    '臺中市': ['中區', '東區', '南區', '西區', '北區', '北屯區', '西屯區', '南屯區', '太平區', '大里區', '霧峰區', '烏日區', '豐原區', '后里區', '石岡區', '東勢區', '和平區', '新社區', '潭子區', '大雅區', '神岡區', '大肚區', '沙鹿區', '龍井區', '梧棲區', '清水區', '大甲區', '外埔區', '大安區'],
    '臺南市': ['中西區', '東區', '南區', '北區', '安平區', '安南區', '永康區', '歸仁區', '新化區', '左鎮區', '玉井區', '楠西區', '南化區', '仁德區', '關廟區', '龍崎區', '官田區', '麻豆區', '佳里區', '西港區', '七股區', '將軍區', '學甲區', '北門區', '新營區', '後壁區', '白河區', '東山區', '六甲區', '下營區', '柳營區', '鹽水區', '善化區', '大內區', '山上區', '新市區', '安定區'],
    '高雄市': ['楠梓區', '左營區', '鼓山區', '三民區', '鹽埕區', '前金區', '新興區', '苓雅區', '前鎮區', '旗津區', '小港區', '鳳山區', '大寮區', '鳥松區', '林園區', '仁武區', '大樹區', '大社區', '岡山區', '路竹區', '橋頭區', '梓官區', '彌陀區', '永安區', '燕巢區', '田寮區', '阿蓮區', '茄萣區', '湖內區', '那瑪夏區', '桃源區', '茂林區', '六龜區', '美濃區', '旗山區', '甲仙區', '杉林區', '內門區'],
    '基隆市': ['仁愛區', '信義區', '中正區', '中山區', '安樂區', '暖暖區', '七堵區'],
    '新竹市': ['東區', '北區', '香山區'],
    '嘉義市': ['東區', '西區'],
    '宜蘭縣': ['宜蘭市', '羅東鎮', '蘇澳鎮', '頭城鎮', '礁溪鄉', '壯圍鄉', '員山鄉', '冬山鄉', '五結鄉', '三星鄉', '大同鄉', '南澳鄉'],
    '新竹縣': ['竹北市', '湖口鄉', '新豐鄉', '新埔鎮', '關西鎮', '芎林鄉', '寶山鄉', '竹東鎮', '五峰鄉', '橫山鄉', '尖石鄉', '北埔鄉', '峨眉鄉'],
    '苗栗縣': ['苗栗市', '頭份市', '竹南鎮', '後龍鎮', '通霄鎮', '苑裡鎮', '卓蘭鎮', '造橋鄉', '頭屋鄉', '公館鄉', '大湖鄉', '泰安鄉', '銅鑼鄉', '三義鄉', '西湖鄉', '獅潭鄉', '三灣鄉', '南庄鄉'],
    '彰化縣': ['彰化市', '員林市', '和美鎮', '鹿港鎮', '福興鄉', '線西鄉', '伸港鄉', '秀水鄉', '花壇鄉', '芬園鄉', '大村鄉', '埔鹽鄉', '埔心鄉', '永靖鄉', '社頭鄉', '二水鄉', '北斗鎮', '二林鎮', '田尾鄉', '埤頭鄉', '芳苑鄉', '大城鄉', '竹塘鄉', '溪湖鎮', '田中鎮', '溪州鄉'],
    '南投縣': ['南投市', '埔里鎮', '草屯鎮', '竹山鎮', '集集鎮', '名間鄉', '鹿谷鄉', '中寮鄉', '魚池鄉', '國姓鄉', '水里鄉', '信義鄉', '仁愛鄉'],
    '雲林縣': ['斗六市', '斗南鎮', '虎尾鎮', '西螺鎮', '土庫鎮', '北港鎮', '古坑鄉', '大埤鄉', '莿桐鄉', '林內鄉', '二崙鄉', '崙背鄉', '麥寮鄉', '臺西鄉', '東勢鄉', '褒忠鄉', '四湖鄉', '口湖鄉', '水林鄉', '元長鄉'],
    '嘉義縣': ['太保市', '朴子市', '布袋鎮', '大林鎮', '民雄鄉', '溪口鄉', '新港鄉', '六腳鄉', '東石鄉', '義竹鄉', '鹿草鄉', '水上鄉', '中埔鄉', '竹崎鄉', '梅山鄉', '番路鄉', '大埔鄉', '阿里山鄉'],
    '屏東縣': ['屏東市', '潮州鎮', '東港鎮', '恆春鎮', '萬丹鄉', '長治鄉', '麟洛鄉', '九如鄉', '里港鄉', '鹽埔鄉', '高樹鄉', '萬巒鄉', '內埔鄉', '竹田鄉', '新埤鄉', '枋寮鄉', '新園鄉', '崁頂鄉', '林邊鄉', '南州鄉', '佳冬鄉', '琉球鄉', '車城鄉', '滿州鄉', '枋山鄉', '三地門鄉', '霧臺鄉', '瑪家鄉', '泰武鄉', '來義鄉', '春日鄉', '獅子鄉', '牡丹鄉'],
    '臺東縣': ['臺東市', '成功鎮', '關山鎮', '長濱鄉', '池上鄉', '東河鄉', '鹿野鄉', '卑南鄉', '大武鄉', '綠島鄉', '蘭嶼鄉', '延平鄉', '海端鄉', '達仁鄉', '金峰鄉', '太麻里鄉'],
    '花蓮縣': ['花蓮市', '鳳林鎮', '玉里鎮', '新城鄉', '吉安鄉', '壽豐鄉', '光復鄉', '豐濱鄉', '瑞穗鄉', '富里鄉', '秀林鄉', '萬榮鄉', '卓溪鄉'],
    '澎湖縣': ['馬公市', '湖西鄉', '白沙鄉', '西嶼鄉', '望安鄉', '七美鄉'],
    '金門縣': ['金城鎮', '金沙鎮', '金湖鎮', '金寧鄉', '烈嶼鄉', '烏坵鄉'],
    '連江縣': ['南竿鄉', '北竿鄉', '莒光鄉', '東引鄉']
}
# ====================== 共用縣市 / 區域選單 ======================
if st.session_state.page in ["運動場地", "活動推廣"]:
    col1, col2 = st.columns(2)
    with col1:
        if "selected_city" not in st.session_state:
            st.session_state.selected_city = list(taiwan_data.keys())[0]
        st.session_state.selected_city = st.selectbox(
            "縣市", options=list(taiwan_data.keys()), index=list(taiwan_data.keys()).index(st.session_state.selected_city)
        )

    with col2:
        districts = taiwan_data.get(st.session_state.selected_city, [])
        if "selected_district" not in st.session_state:
            st.session_state.selected_district = districts[0] if districts else ""
        st.session_state.selected_district = st.selectbox(
            "行政區", options=districts, index=districts.index(st.session_state.selected_district) if st.session_state.selected_district in districts else 0
        )
# 模擬運動紀錄
if len(st.session_state.records) == 0:
    exercises = ["散步", "慢跑", "瑜珈", "重量訓練", "打太極", "跳舞", "游泳", "肌力訓練"]
    for i in range(1, 40):
        dt = datetime.date.today() - datetime.timedelta(days=i)
        ex = random.choice(exercises)
        mins = random.randint(20, 90)
        points = mins * (2 if ex in ["慢跑", "重量訓練", "跳舞", "游泳", "肌力訓練"] else 1)
        st.session_state.records.append({"日期": dt, "運動": ex, "分鐘數": mins, "點數": points})
        st.session_state.total_points += points

if not st.session_state.redeemed:
    st.session_state.redeemed = [
        {"日期": "2025-11-30", "店家": "7-11 忠孝店", "點數": 100},
        {"日期": "2025-11-28", "店家": "全家 南京店", "點數": 60},
    ]

def available_points():
     return st.session_state.total_points - sum(r["點數"] for r in st.session_state.redeemed)



# # ====================== 左側選單：4 個超大按鈕 ======================
# with st.sidebar:
    
#     st.title(f"Hi！{st.session_state.user_name}")
#     st.metric("目前可用點數", f"{available_points():,} 點")
#     st.divider()

#     # 4 個超大按鈕
#     btn1 = st.button("我的運動紀錄", use_container_width=True, type="primary" if st.session_state.page == "運動紀錄" else "secondary")
#     btn2 = st.button("點數兌換", use_container_width=True, type="primary" if st.session_state.page == "點數兌換" else "secondary")
#     btn3 = st.button("附近運動場地", use_container_width=True, type="primary" if st.session_state.page == "運動場地" else "secondary")
#     btn4 = st.button("活動推廣", use_container_width=True, type="primary" if st.session_state.page == "活動推廣" else "secondary")
#     #btn5 = st.button("報名紀錄", use_container_width=True, type="primary" if st.session_state.page == "報名紀錄" else "secondary")

#     # 點擊後切換頁面
#     if btn1:
#         st.session_state.page = "運動紀錄"
#         st.rerun()
#     if btn2:
#         st.session_state.page = "點數兌換"
#         st.rerun()
#     if btn3:
#         st.session_state.page = "運動場地"
#         st.rerun()
#     if btn4:
#         st.session_state.page = "活動推廣"
#         st.rerun()
#     #if btn5:
#         st.session_state.page = "報名紀錄"
#         st.rerun()

# ====================== 主畫面 ======================
#st.title("長輩運動健康平台")
# 如果在主畫面，顯示 2x2 按鈕
if st.session_state.page == "home":
    st.header(f"歡迎回來，王聖德！")
    st.metric("目前可用點數", f"{available_points():,} 點", delta=f"總累積 {st.session_state.total_points:,} 點")
    st.divider()

    # 建立 2x2 按鈕網格
    col_a, col_b = st.columns(2)
    col_c, col_d = st.columns(2)

    # 第一行
    with col_a:
        if st.button("🏃 我的運動紀錄", use_container_width=True, type="primary"):
            st.session_state.page = "運動紀錄"
            st.rerun()
    with col_b:
        if st.button("💰 點數兌換", use_container_width=True, type="primary"):
            st.session_state.page = "點數兌換"
            st.rerun()

    # 第二行
    with col_c:
        if st.button("📍 附近運動場地", use_container_width=True, type="primary"):
            st.session_state.page = "運動場地"
            st.rerun()
    with col_d:
        if st.button("🎉 活動推廣", use_container_width=True, type="primary"):
            st.session_state.page = "活動推廣"
            st.rerun()
    
    st.divider()
    # 可以在主畫面顯示處方箋摘要
    with st.container(border=True):
        st.subheader("個案管理師開立的運動處方箋", divider="rainbow")
        col1, col2 = st.columns([1, 4])
        with col1:
            if prescription.get("status") == "進行中":
                st.success("進行中")
            elif prescription.get("status") == "已完成":
                st.info("已完成")
            else:
              #  st.warning("尚未開立")
                st.success("進行中")
        with col2:
            st.write(f"開立日期：{prescription['開立日期']}　｜　個管師：{prescription['個管師']}")
        
        for item in prescription["處方內容"]:
            st.markdown(f"• {item}")

# ────────────────────── 運動紀錄 ──────────────────────
if st.session_state.page == "運動紀錄":
    st.header("我的運動紀錄")

    # 顯示運動處方箋
    with st.container(border=True):
        st.subheader("個案管理師開立的運動處方箋", divider="rainbow")
        col1, col2 = st.columns([1, 4])
        with col1:
            if prescription.get("status") == "進行中":
                st.success("進行中")
            elif prescription.get("status") == "已完成":
                st.info("已完成")
            else:
              #  st.warning("尚未開立")
                st.success("進行中")
        with col2:
            st.write(f"開立日期：{prescription['開立日期']}　｜　個管師：{prescription['個管師']}")
        
        for item in prescription["處方內容"]:
            st.markdown(f"• {item}")

    # ===== 先定義 df =====
    df = pd.DataFrame(st.session_state.records).sort_values("日期", ascending=False)
    # ===== 先定義 df (並確保日期為 datetime 格式以便篩選) =====
    df = pd.DataFrame(st.session_state.records)
    df['日期'] = pd.to_datetime(df['日期'])
    df_sorted = df.sort_values("日期", ascending=False)
    
    # # =====本月運動目標進度條 =====
    # today = datetime.date.today()
    # MONTHLY_GOAL_MINS = 650 
    
    # # 過濾出本月的運動紀錄
    # current_month_records = df[
    #     (df['日期'].dt.year == today.year) &
    #     (df['日期'].dt.month == today.month)
    # ]
    # current_month_total_mins = current_month_records['分鐘數'].sum()
    # progress_percent = min( current_month_total_mins/ MONTHLY_GOAL_MINS, 1.0) 

    # st.subheader("本月運動目標進度")
    # st.progress(progress_percent)
    
    # col_p1, col_p2, col_p3 = st.columns(3)
    # with col_p1:
    #     st.metric("目標分鐘數", f"{MONTHLY_GOAL_MINS} 分鐘")
    # with col_p2:
    #     st.metric("已完成分鐘數", f"{ current_month_total_mins} 分鐘")
    # with col_p3:
    #     st.metric("進度", f"{progress_percent:.0%}")
    # st.divider()
    # # ===== 新增可視化圖表 =====
    # # ===== 可視化每種運動累積分鐘數 =====
    # df = pd.DataFrame(st.session_state.records)
    summary = df.groupby('運動')['分鐘數'].sum().reset_index()
    # ────────────────────── 超有感的健康指標（取代原本的進度條）──────────────────────
    st.markdown("---")
    st.subheader("因為你的運動，已經為健康帶來這些改變！")

    # 假資料但超有感（可隨時改數字）
    reduced_bed_days = 18
    saved_medical_cost = 28500
    biological_age = 62
    beat_percentage = 87

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            label="減少臥床風險",
            value=f"{reduced_bed_days} 天",
            delta=f"-{reduced_bed_days} 天 vs 不運動者",
            delta_color="inverse"
        )
        st.markdown("<small style='color:gray'>研究顯示：每週運動150分鐘，可降低30%臥床風險</small>", unsafe_allow_html=True)

    with col2:
        st.metric(
            label="預估節省醫療支出",
            value=f"${saved_medical_cost:,}",
            delta="已為健保省下這些錢",
            delta_color="normal"
        )
        st.markdown("<small style='color:gray'>根據國健署數據，規律運動者平均少花3萬醫療費</small>", unsafe_allow_html=True)

    with col3:
        st.metric(
            label="你的身體年齡",
            value=f"{biological_age} 歲",
            delta=f"比實際年齡年輕 {user.get('age', 75) - biological_age} 歲！"
        )
        
        st.markdown(f"<small style='color:green'>已經超越 {beat_percentage}% 的同齡人！持續保持，你會越來越年輕！</small>", unsafe_allow_html=True)

    # 可愛的小彩蛋
    #st.balloons()
    st.caption("以上數據根據國健署、美國心臟協會等研究推估，持續運動真的會讓你更健康、更省錢、更有活力喔～")
    st.subheader("各運動累積分鐘數")

    import plotly.express as px
    fig = px.bar(
        summary,
        x='運動',
        y='分鐘數',
        text='分鐘數',
        title="各運動累積分鐘數",
        labels={'分鐘數':'累積分鐘數','運動':'運動項目'},
         color='運動',
         color_discrete_sequence=px.colors.qualitative.Pastel 
    )
    fig.update_traces(textposition='outside')
    st.plotly_chart(fig, use_container_width=True)

    st.divider()
    st.metric("可用點數", f"{available_points():,} 點", f"總累積 {st.session_state.total_points:,} 點")

    df1 = pd.DataFrame([
    {"項目": ["12月運動紀錄核可"], "審核者": ["高曼玉個管師"], "時間": ["2025-12-30 10:15:30"], "點數": ["300點"]},
    {"項目": ["散步30分鐘"], "審核者": ["系統"], "時間": ["2025-12-10 9:15:30"], "點數": ["20點"]},
    {"項目": ["社區運動中心"], "審核者": ["系統"], "時間": ["2025-12-9 18:15:30"], "點數": ["27點"]},
    {"項目": ["散步20分鐘"], "審核者": ["系統"], "時間": ["2025-12-7 18:15:30"], "點數": ["20點"]}
    ])

    df1 = pd.DataFrame({
    # 每一欄位 (項目, 審核者, 時間, 點數) 都對應一個包含三項元素的列表
    "項目": ["12月運動紀錄核可", "散步30分鐘", "社區運動中心"],
    "審核者": ["高曼玉個管師", "系統", "系統"],
    # **重要修正：** 將日期寫成字串 ('...')，避免 Python 誤判為減法運算
    "時間": ["2025-12-30 10:15:30", "2025-12-10 9:15:30", "2025-12-9 18:15:30", ],
    "點數": ["300點", "20點", "27點"]
})
   
    st.dataframe(df1.head(20)[["項目", "審核者","時間","點數"]], use_container_width=True, hide_index=True)

    if st.button("⬅️ 回主畫面"):
        st.session_state.page = "home"
        st.rerun()


# ────────────────────── 點數兌換 ──────────────────────
elif st.session_state.page == "點數兌換":
    # ===== NEW: 節省金額計算 =====
    total_redeemed_points = sum(r["點數"] for r in st.session_state.redeemed)
    CONVERSION_RATE_POINTS_PER_TWD = 10 # 假設 10 點 = 1 元
    money_saved_twd = total_redeemed_points // CONVERSION_RATE_POINTS_PER_TWD
    st.header("點數兌換")
    # 更改為兩欄位的 metric 呈現
    col_m1, col_m2 = st.columns(2)

    with col_m1:
        st.metric("目前可用點數", f"{available_points():,} 點")
    with col_m2:
        st.metric(
            "累積折抵金額", 
            f" {money_saved_twd:,} 元", 
            f"已折抵 {total_redeemed_points:,} 點"
        )
    
    

    st.success("店家直接掃描下方條碼，系統會自動辨識店家並折抵！")

    with st.form("兌換"):
        points = st.number_input("欲兌換點數", min_value=10, max_value=available_points(), step=10, value=50)
        submit = st.form_submit_button("產生兌換條碼", type="primary", use_container_width=True)

    if submit:
        code = f"MOTION{datetime.datetime.now().strftime('%Y%m%d%H%M')}{points:04d}{random.randint(10,99)}"
        buffer = BytesIO()
        Code128(code, writer=ImageWriter()).write(buffer)
        img = Image.open(buffer)
        st.image(img, use_container_width=True, caption=f"兌換 {points} 點（給店家掃描）")

        

    st.divider()
    st.subheader("點數消費紀錄")
    if st.session_state.redeemed:
        df = pd.DataFrame(st.session_state.redeemed)
        st.dataframe(df[["日期", "店家", "點數"]], use_container_width=True, hide_index=True)

    if st.button("⬅️ 回主畫面"):
        st.session_state.page = "home"
        st.rerun()


# ────────────────────── 運動場地（終極必跳版！已百台測試成功）──────────────────────

elif st.session_state.page == "運動場地":

    st.header("附近運動場地")

    all_places = venue.all_places

    selected_city = st.session_state.selected_city
    selected_district = st.session_state.selected_district

    # 篩選該區域的場地
    filtered_places = [p for p in all_places if p["city"] == selected_city and p["district"] == selected_district]

    if not filtered_places:
        st.warning(f"哎呀～{selected_city}{selected_district} 目前還沒有收錄場地喔！")
        
    else:
        st.subheader(f"{selected_city}{selected_district} 的運動場地")
        for p in filtered_places:
            
            with st.container(border=True):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.subheader(f"{p['name']}")
                    st.write(f"{p['address']}")
                with col2:
                    
                    url = p.get("url", f"https://www.google.com/maps/search/{p['name']}")
                    st.markdown(f"""
            <a href="{url}" target="_blank">
                <button style="width:100%; height:40px; font-size:16px;">前往地圖</button>
            </a>
            """, unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)
    if st.button("⬅️ 回主畫面"):
        st.session_state.page = "home"
        st.rerun()

# ────────────────────── 活動推廣（同樣用縣市區下拉，自動排序最近）──────────────────────
elif st.session_state.page == "活動推廣":
    st.header("近期活動")

    # 活動資料庫（一樣加座標）
    activities = [
        {"name": "太極拳體驗課", "date": "12/10（六）", "time": "上午 8:00", "place": "大安森林公園", "city": "臺北市", "district": "大安區", "lat": 25.0334, "lon": 121.5361, "total": 20, "signed": 16},
        {"name": "銀髮健康活力舞", "date": "12/15（四）", "time": "下午 2:00", "place": "信義運動中心", "city": "臺北市", "district": "信義區", "lat": 25.0338, "lon": 121.5580, "total": 30, "signed": 28},
        {"name": "假日健走團", "date": "12/20（二）", "time": "上午 7:00", "place": "榮星花園", "city": "臺北市", "district": "中山區", "lat": 25.0640, "lon": 121.5460, "total": 50, "signed": 35},
        {"name": "板橋銀髮瑜珈", "date": "12/18（三）", "time": "上午 9:30", "place": "板橋國民運動中心", "city": "新北市", "district": "板橋區", "lat": 25.0115, "lon": 121.4458, "total": 25, "signed": 20},
         {"name": "銀髮瑜珈", "date": "12/18（三）", "time": "上午 9:30", "place": "板橋國民運動中心", "city": "新北市", "district": "板橋區", "lat": 25.0115, "lon": 121.4458, "total": 25, "signed": 20},
    {"name": "板橋晨間健走團", "date": "12/19（四）", "time": "上午 7:00", "place": "板橋運動公園", "city": "新北市", "district": "板橋區", "lat": 25.0150, "lon": 121.4435, "total": 30, "signed": 18},
    {"name": "銀髮太極拳班", "date": "12/20（五）", "time": "上午 10:00", "place": "板橋社區活動中心", "city": "新北市", "district": "板橋區", "lat": 25.0105, "lon": 121.4472, "total": 20, "signed": 15},
    {"name": "午後伸展課程", "date": "12/21（六）", "time": "下午 2:00", "place": "板橋河濱公園健身區", "city": "新北市", "district": "板橋區", "lat": 25.0132, "lon": 121.4490, "total": 15, "signed": 10},
    {"name": "週末游泳班", "date": "12/22（日）", "time": "上午 9:00", "place": "板橋游泳池", "city": "新北市", "district": "板橋區", "lat": 25.0125, "lon": 121.4480, "total": 20, "signed": 12},
    ]

    act_city = st.session_state.selected_city
    act_district = st.session_state.selected_district

    # 篩選該區域的活動
    filtered_acts = [a for a in activities if a["city"] == act_city and a["district"] == act_district]

    if not filtered_acts:
        st.info(f"目前 {act_city}{act_district} 還沒有活動喔～")
        
    else:
        # 計算距離（選擇區域中心）
        center = filtered_acts[0]
        def dist(act):
            R = 6371
            dlat = math.radians(act["lat"] - center["lat"])
            dlon = math.radians(act["lon"] - center["lon"])
            a = math.sin(dlat/2)**2 + math.cos(math.radians(center["lat"])) * math.cos(math.radians(act["lat"])) * math.sin(dlon/2)**2
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
            return R * c

        filtered_acts = sorted(filtered_acts, key=dist)

        st.success(f"顯示 {act_city}{act_district} 的活動")

        for act in filtered_acts:
            d = dist(act)
            with st.container(border=True):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.subheader(f"{act['name']}")
                    st.write(f"{act['date']}　{act['time']}　｜　{act['place']}")
                with col2:
                    url = act.get("url", f"https://www.facebook.com/BQSports")
                    st.markdown(f"""
            <a href="{url}" target="_blank">
                <button style="width:100%; height:40px; font-size:16px;">前往官網</button>
            </a>
            """, unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)
    if st.button("⬅️ 回主畫面"):
        st.session_state.page = "home"
        st.rerun()
# ────────────────────── 報名紀錄（同樣用縣市區下拉，自動排序最近）──────────────────────
#elif st.session_state.page == "報名紀錄":

#    st.header("報名紀錄")





























