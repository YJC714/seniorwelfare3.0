import streamlit as st
import pandas as pd
import datetime
import random
from io import BytesIO
from PIL import Image
from barcode import Code128
from barcode.writer import ImageWriter
import pydeck as pdk
import math
import venue
from venue import all_places
import plotly.express as px

# ====================== 設置 GSheet 連線與資料讀取 ======================
import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

st.markdown("""
    <style>
    /* 1. 強制放大所有按鈕內的文字 (包含普通按鈕與連結按鈕) */
    div[data-testid="stButton"] button p, 
    div[data-testid="stLinkButton"] a p,
    div[data-testid="stBaseButton-primary"] p,
    div[data-testid="stBaseButton-secondary"] p {
        font-size: 35px !important;
        font-weight: bold !important;
    }

    /* 2. 針對按鈕本身的高度調整，避免字體太大被切掉 */
    div[data-testid="stButton"] button, 
    div[data-testid="stLinkButton"] a {
        min-height: 100px !important;
        border-radius: 20px !important;
    }

    /* 3. 放大 Metric (點數看板) 的數字與標籤 */
    div[data-testid="stMetricValue"] {
        font-size: 50px !important;
        color: #FF4B4B !important; /* 讓數字變紅色更明顯 */
    }
    div[data-testid="stMetricLabel"] p {
        font-size: 28px !important;
        font-weight: bold !important;
    }

    /* 4. 放大一般 Markdown 文字與說明 */
    .stMarkdown p, .stMarkdown li {
        font-size: 24px !important;
        line-height: 1.6 !important;
    }
    
    /* 5. 放大下拉選單 (Selectbox) 的文字 */
    div[data-testid="stSelectbox"] label p {
        font-size: 26px !important;
        font-weight: bold !important;
    }
    div[data-baseweb="select"] > div {
        font-size: 24px !important;
    }
    </style>
""", unsafe_allow_html=True)


# 1. 建立連線實例 (只需要一次)
conn = st.connection("gsheets", type=GSheetsConnection)
# ----------------------------------------------------
# 2. 讀取工作表 

df_prescriptions = conn.read(worksheet="prescriptions", header=0)
df_patients = conn.read(worksheet="patients", header=0)
# 🎯 新增：讀取活動推廣表
df_activities_raw = conn.read(worksheet="activities", header=0) 

# 清理欄位名稱


# 目前使用的長者ID
CURRENT_PATIENT_ID = "4.0"

def clean_column_names(df: pd.DataFrame) -> pd.DataFrame:
    # 將所有欄位名稱轉為小寫並移除前後空格
    df.columns = [col.strip().lower() for col in df.columns]
    return df

# 【轉換 1: 個案基本資料】
def transform_patients_data(df: pd.DataFrame) -> dict:
    if 'patient_num' not in df.columns:
        st.error("請檢查資料庫標題列，找不到 patient_num。")
        return {}

    # 關鍵修正：先強制轉換索引為字串，再轉成字典
    df['patient_num'] = df['patient_num'].astype(str) 
    patients_dict = df.set_index('patient_num').to_dict('index')
    return patients_dict

# 【轉換 2: 處方箋資料】
def transform_prescriptions_data(df: pd.DataFrame) -> dict:
    if not all(col in df.columns for col in ['case_manager', 'patient_num', 'content']):
        st.error("請檢查資料庫標題列。")
        return {}
    
    # 強制格式化 ID 為 "1.0"
    def force_to_one_decimal_str(val):
        try:
            return f"{float(val):.1f}"
        except:
            return str(val).strip()

    df['patient_num'] = df['patient_num'].apply(force_to_one_decimal_str)
    
    # 處理內容
    df['content'] = df['content'].apply(
        lambda x: [item.strip() for item in str(x).split(',') if item.strip()]
    )
    
    prescriptions_all = {}
    grouped = df.groupby(['case_manager', 'patient_num'])
    
    for (manager_id, patient_id), group in grouped:
        # 這裡會保留除了分組欄位以外的所有欄位（包含日期）
        pres_list = group.to_dict('records') 
        
        if manager_id not in prescriptions_all:
            prescriptions_all[manager_id] = {}
        prescriptions_all[manager_id][patient_id] = pres_list
        
    return prescriptions_all
def get_exercise_report(conn, current_patient_id):
    # 讀取運動報表
    df_report = conn.read(worksheet="exercise_report", header=0)
    # 欄位標準化
    df_report.columns = [c.strip().lower() for c in df_report.columns]
    # 確保 ID 格式一致
    df_report['patient_num'] = df_report['patient_num'].astype(str)
    # 篩選特定長者
    user_report = df_report[df_report['patient_num'] == str(current_patient_id)].copy()
    return user_report

def available_points():
    # 🎯 模擬前幾個月累積 (固定 500)
    past_months_points = 500 
    # 本月 (12月) 的運動分 (1分鐘=1點)
    current_month_pts = st.session_state.get("total_points_auto", 0)
    # 扣除已經兌換掉的
    used_pts = sum(r.get("點數", 0) for r in st.session_state.get("redeemed", []))
    return int(past_months_points + current_month_pts - used_pts)
def update_health_indicators(df, current_age):
    if df.empty:
        st.session_state.body_age = current_age
        st.session_state.reduced_bed_days = 0
        st.session_state.saved_medical_cost = 0
        st.session_state.beat_percentage = 0
        return

    total_min = df['minute'].sum()
    
    # 這是你原本的邏輯整理
    st.session_state.reduced_bed_days = round(total_min * 0.02, 1)  # 每50分鐘換1天
    st.session_state.saved_medical_cost = int(total_min * 10)       # 每分鐘省10元
    # 身體年齡：每運動 100 分鐘減 1 歲，最多減到 50 歲
    st.session_state.body_age = max(50, current_age - int(total_min / 100))
    # 超越百分比
    st.session_state.beat_percentage = min(99, int(total_min / 10)) # 假設10分鐘贏1%
df_patients = clean_column_names(df_patients)
df_prescriptions = clean_column_names(df_prescriptions)
df_activities = clean_column_names(df_activities_raw) # 🎯 確保欄位是小寫

# 初始化 view 狀態
if "view" not in st.session_state:
    st.session_state.view = "home"  # 預設顯示主畫面    
# ====================== 執行資料轉換與長者資料初始化 (解決未定義變數問題) ======================



# 執行轉換
patients_data = transform_patients_data(df_patients)


prescriptions_all = transform_prescriptions_data(df_prescriptions)


# 取得這位長者的完整資料 (GSheet 欄位名稱要對應)
user = patients_data.get(CURRENT_PATIENT_ID)

if not user:
    st.error("找不到該名長者的資料，請確認 ID 是否正確")
    st.stop()

# 設定姓名顯示
st.session_state.user_name = user.get("name", "長者")


# 關鍵：取得負責的個管師
case_manager_id = user.get("case_manager", None)  

# 取得該個管師為這位長者開的處方（取最新一筆）
prescription = None
if case_manager_id and case_manager_id in prescriptions_all:
    patient_pres_list = prescriptions_all[case_manager_id].get(CURRENT_PATIENT_ID, [])
    if patient_pres_list:
        prescription = patient_pres_list[-1]  # 最新一筆


# 如果沒有處方箋，就顯示預設訊息
if not prescription:
    prescription = {
        "prescription_date": "尚未開立",
        "case_manager": user.get("case_manager", "尚未指派"),
        "content": ["請聯繫您的個管師開立運動處方箋"],
        "minute": 0,
        "frequency": 0
    }
else:
    # 🎯 補強：確保即使抓到資料，也要轉換成正確格式
    # 如果抓不到(None)，才使用預設值
    p_date = prescription.get("prescription_date")
    prescription["prescription_date"] = str(p_date) if p_date else "2025-12-01"
    
    # 處理頻率：轉為整數
    try:
        prescription["frequency"] = int(float(prescription.get("frequency", 3)))
    except:
        prescription["frequency"] = 3
        
    # 處理分鐘：轉為整數
    try:
        prescription["minute"] = int(float(prescription.get("minute", 30)))
    except:
        prescription["minute"] = 30
        
    # 處理內容：如果是字串就轉 List (預防萬一)
    if isinstance(prescription.get("content"), str):
        prescription["content"] = [item.strip() for item in prescription["content"].split(",")]




# ====================== 初始化 (保持不變) ======================
for key, default_value in {
    "records": [], 
    "redeemed": [], 
    "total_points": 0, 
    "user_name": "訪客", # 這裡改為通用稱呼
    "page": "運動紀錄"
}.items():
    if key not in st.session_state:
        st.session_state[key] = default_value
if user:
    # 1. 基礎資訊
    st.session_state.user_name = user.get("name", "長者")
    st.session_state.current_age = user.get("age", 75)
    
    # 2. 點數資訊 (對應你的 GSheet 欄位)
    # 我們將欄位轉為數字，避免 GSheet 讀進來變成字串
    st.session_state.total_points_auto = pd.to_numeric(user.get("total_points_auto", 0))
    st.session_state.total_points_pending = pd.to_numeric(user.get("total_points_pending", 0))
    st.session_state.total_points = pd.to_numeric(user.get("total_points", 0))
    
        

# ====================== 共用縣市 / 區域選單 ======================
def city_district_selector():
    if st.session_state.view in ["運動場地", "活動推廣"]:
        col1, col2 = st.columns(2)
        with col1:
            if "selected_city" not in st.session_state:
                st.session_state.selected_city = list(venue.taiwan_data.keys())[0]
            st.session_state.selected_city = st.selectbox(
                "縣市", options=list(venue.taiwan_data.keys()), index=list(venue.taiwan_data.keys()).index(st.session_state.selected_city)
            )

        with col2:
            districts = venue.taiwan_data.get(st.session_state.selected_city, [])
            if "selected_district" not in st.session_state:
                st.session_state.selected_district = districts[0] if districts else ""
            st.session_state.selected_district = st.selectbox(
                "行政區", options=districts, index=districts.index(st.session_state.selected_district) if st.session_state.selected_district in districts else 0
            )
def back_to_home():
    # 建立兩欄，比例為 4:1 (讓按鈕靠右)
    col_back, col_title  = st.columns([1, 4])
    with col_back:
        # 使用 primary 顏色讓它在大一點的同時更顯眼
        if st.button("🏠 返回主頁", use_container_width=True, type="primary", key="back_btn_universal"):
            st.session_state.view = "home"
            st.rerun()

def update_points_logic(patient_id, report_df, prescription_content):
    if report_df.empty:
        return 0, 0

    # 1. 確保日期格式
    report_df['date'] = pd.to_datetime(report_df['date'])
    
    # 2. 只篩選 12 月紀錄
    dec_df = report_df[report_df['date'].dt.month == 12].copy()
    
    # 3. 符合處方才算分 (1 分鐘 = 1 點)
    def is_prescribed(ex_name):
        return any(pres in str(ex_name) for pres in prescription_content)
    
    dec_df['is_match'] = dec_df['exercise_name'].apply(is_prescribed)
    
    # 🎯 這裡就是你要的 1:1 換算
    auto_pts = int(dec_df[dec_df['is_match'] == True]['minute'].sum())
    
    # 獎勵分暫設為 0，除非你有特定加碼邏輯
    pending_pts = 0 
    
    return auto_pts, pending_pts

    

# ====================== 主畫面 ======================

st.set_page_config(page_title="運動健康系統", page_icon="🏃", layout="wide")





# ==================== 主畫面（預設頁）====================
if st.session_state.view == "home":
    st.title("🏃‍♂️ 運動健康管理系統")
    st.markdown(f"### Hi！{st.session_state.user_name}，今天也要動一動喔～")

    # 處方箋顯示（簡潔版）
    with st.container(border=True):
        st.subheader("個案管理師開立的運動處方箋", divider="rainbow")
        p_date = prescription.get('prescription_date', '尚未開立')
        p_manager = prescription.get('case_manager_name', prescription.get('case_manager', '未指派'))
        p_freq = prescription.get("frequency", 0)
        p_min = prescription.get("minute", 0)
        content_str = "、".join(prescription.get("content", ["請聯繫個管師開立處方"]))

        st.write(f"📅 開立日期：{p_date}　｜　👤 個管師：{p_manager}")
        st.info(f"🚀 運動目標：每週進行 {content_str}，共 {p_freq} 次，每次 {p_min} 分鐘")

    st.markdown("### 請選擇功能")
    
    # 四個超大按鈕
    col1, col2 = st.columns(2)
    col3, col4 = st.columns(2)

    with col1:
        if st.button("🏃‍♂️ 我的運動紀錄", use_container_width=True, type="primary"):
            st.session_state.view = "運動紀錄"
            st.rerun()
    with col2:
        if st.button("🎁 點數兌換", use_container_width=True, type="primary"):
            st.session_state.view = "點數兌換"
            st.rerun()
    with col3:
        if st.button("🗺️ 附近運動場地", use_container_width=True, type="primary"):
            st.session_state.view = "運動場地"
            st.rerun()
    with col4:
        if st.button("📢 活動推廣", use_container_width=True, type="primary"):
            st.session_state.view = "活動推廣"
            st.rerun()

# ==================== 詳細頁面 ====================

# 返回主畫面的按鈕（所有詳細頁共用）


# ───── 我的運動紀錄 ─────
elif st.session_state.view == "運動紀錄":
     back_to_home()
     st.header("🏃‍♂️ 我的運動紀錄")

        # 每次進入此頁都強制重新計算點數（保證最新）
     user_report_df = get_exercise_report(conn, CURRENT_PATIENT_ID)
     auto_pts, pending_pts = update_points_logic(CURRENT_PATIENT_ID, user_report_df, prescription.get("content", []))
     calculated_pending = int(auto_pts / 4 * 6)
     st.session_state.total_points_auto = int(auto_pts)
     st.session_state.total_points_pending = calculated_pending
     st.session_state.records = user_report_df.to_dict('records')
     
     # ==================== 新增：點數概況看板 ====================
     with st.container(border=True):
        # 建立三欄位顯示不同類型的點數
        c1, c2, c3 = st.columns(3)
        
        # 目前總共可用的點數 (調用你定義的 available_points 函式)
        c1.metric("💰 目前可用點數", f"{available_points():,} 點")
        
        # 本月自動核發的運動分
        c2.metric("✨ 本月系統發放點數", f"{st.session_state.total_points_auto:,} 點", help="系統根據運動紀錄自動換算的點數")
        
        # 待審核的獎勵分
        # 如果 pending_pts > 0，顯示綠色箭頭增加感
        c3.metric("⏳ 待個管師審核點數", f"{st.session_state.total_points_pending:,} 點", delta_color="normal")
    # =========================================================

        # 手動重新整理按鈕
     if st.button("🔄 重新整理運動紀錄與點數", use_container_width=True):
        st.success("已重新整理最新紀錄！")
        st.rerun()


    
    # 3. 強制更新 session_state（保證一定有這個變數）
     st.session_state.total_points_auto = int(auto_pts)
     st.session_state.total_points_pending = int(pending_pts)
     st.session_state.records = user_report_df.to_dict('records')
    # 🔧 除錯區塊（測試完可刪）
    # 🔧 強制展開的除錯區塊
     if "total_points_auto" in st.session_state:
        del st.session_state.total_points_auto
     if "total_points_pending" in st.session_state:
        del st.session_state.total_points_pending
    
    
    # 3. 強制更新 Session (這樣側邊欄才會立刻變)
     st.session_state.total_points_auto = auto_pts
     st.session_state.total_points_pending = pending_pts
    
    # 將抓到的資料轉存到 session 供後續繪圖使用
     st.session_state.records = user_report_df.to_dict('records')

    # --- 步驟 2: 處方箋顯示 (保持你原本的代碼) ---
     with st.container(border=True):
        st.subheader("個案管理師開立的運動處方箋", divider="rainbow")
        
        # 取得資料
        p_date = prescription.get('prescription_date', 'N/A')
        p_manager = prescription.get('case_manager_name', '未指派')
        p_freq = prescription.get("frequency", 0)
        p_min = prescription.get("minute", 0)
        
        # 顯示基本資訊
        st.write(f"📅 開立日期：{p_date}　｜　👤 個管師：{p_manager}")
        
        # 🎯 這裡就是你要的格式：每週幾次、每次幾分鐘
        # 使用 st.info 讓它有個藍色底框，長者看得比較清楚
        for item in prescription.get("content", ["無處方內容"]):
          st.info(f"🚀 運動目標：  每週 {item} {p_freq} 次，每次 {p_min} 分鐘")
        
        

    # --- 步驟 3: 資料處理與處方達成率計算 ---
     if not user_report_df.empty:
        # 確保型態正確
        user_report_df['minute'] = pd.to_numeric(user_report_df['minute'], errors='coerce').fillna(0)
        user_report_df['date'] = pd.to_datetime(user_report_df['date'])
        
        # 🎯 新增：取得處方日期並過濾
        full_history_df = user_report_df.sort_values("date", ascending=False)
        p_date_raw = prescription.get("prescription_date")
        try:
            # 將處方日期轉為 datetime 格式
            p_date = pd.to_datetime(p_date_raw)
            
            # 只保留「運動日期 >= 處方開立日期」的紀錄
            filtered_df = user_report_df[user_report_df['date'] >= p_date].copy()
        except:
            # 如果日期格式有誤，就不過濾，避免程式當掉
            filtered_df = user_report_df.copy()

        # 如果過濾後還有資料，才進行後續計算
        if not filtered_df.empty:
            p_min_goal = pd.to_numeric(prescription.get("minute", 0))
            p_freq_num = pd.to_numeric(prescription.get("frequency", 0))
            target_days_monthly = 28 if p_freq_num == 7 else p_freq_num * 4

            # 2. 計算合格天數 (當天運動總分鐘數 >= 處方要求分鐘數)
            daily_total = filtered_df.groupby(filtered_df['date'].dt.date)['minute'].sum().reset_index()
            qualified_days = daily_total[daily_total['minute'] >= p_min_goal].shape[0]
            
            # 3. 計算達成率
            progress_rate = min(1.0, qualified_days / target_days_monthly) if target_days_monthly > 0 else 0
            
            # 4. 排序與健康指標
            df_sorted = filtered_df.sort_values("date", ascending=False)
            summary = filtered_df.groupby('exercise_name')['minute'].sum().reset_index()
            update_health_indicators(filtered_df, user.get("age", 75))
            st.session_state.beat_percentage = min(99, int(filtered_df['minute'].sum() / 10))
        else:
            qualified_days, target_days_monthly, progress_rate = 0, 0, 0
            df_sorted = pd.DataFrame() # 空表格
            summary = pd.DataFrame()
     else:
        qualified_days, target_days_monthly, progress_rate = 0, 0, 0
        df_sorted = pd.DataFrame()
        summary = pd.DataFrame()

    # --- 步驟 4: 顯示健康指標 (Metric) ---
     st.markdown("---")
     st.subheader("因為你的運動，已經為健康帶來這些改變！")
     age_diff = user.get('age', 75) - st.session_state.body_age
     c1, c2, c3 = st.columns(3)
     c1.metric("減少臥床風險", f"{st.session_state.reduced_bed_days} 天")
     c2.metric("預估節省醫療支出", f"${st.session_state.saved_medical_cost:,}")
     c3.metric("你的身體年齡", f"{st.session_state.body_age} 歲")
    # 3. 將鼓勵文字放在指標下方，看起來更溫馨
     if age_diff > 0:
        c3.write(f"✨ 比實際年齡年輕了 {age_diff} 歲！")
     else:
        c3.write("✨ 狀態維持得很好，繼續運動喔！")
    
     st.success(f"🔥 你已經超越了 {st.session_state.beat_percentage}% 的同齡人！")
    # 找到 st.success(f"🔥 你已經超越了...") 下方加入：
     st.markdown("---")
     st.subheader("本月處方執行進度")
    
    # 假設處方要求一個月 20 天，計算實際天數
    # 找到「本月處方執行進度」區塊，修改顯示文字
    # --- 重新定義分子：符合處方且在12月的運動天數 ---

     if not user_report_df.empty:
        # 1. 定義比對邏輯（檢查運動名稱是否在處方清單中）
        prescription_content = prescription.get("content", [])
        def is_prescribed(ex_name):
            return any(pres in str(ex_name) for pres in prescription_content)

    # 2. 執行過濾
    # 條件 A: 符合處方項目
    # 條件 B: 日期是在 12 月 (month == 12)
     mask_match = user_report_df['exercise_name'].apply(is_prescribed)
     mask_december = user_report_df['date'].dt.month == 12
    
    # 3. 篩選出符合條件的紀錄
     matched_dec_df = user_report_df[mask_match & mask_december]

    # 4. 計算不重複的活躍天數 (分子)
     active_days = matched_dec_df['date'].dt.date.nunique()
    
    # --- 分母維持不變 ---
     display_target = p_freq_num * 4 if p_freq_num > 0 else 20 
     display_rate = min(1.0, active_days / display_target)

    # 5. 顯示進度條
     st.progress(display_rate, text=f"12月處方運動活躍天數：{active_days} 天")
    
    # 💡 增加一個貼心提醒，告訴長者哪些被計入了
     if active_days > 0:
        st.caption(f"✅ 已採計包含「{', '.join(prescription_content)}」的 12 月紀錄")
     else:
        st.warning("⚠️ 目前 12 月尚未有符合處方項目的運動紀錄喔！")
        st.write("✨ 保持規律運動，身體會感謝你的努力！") # 拿掉「核發全額」等過於明確的字眼

    # --- 步驟 5: 顯示圖表 (修正 Plotly 欄位) ---
     st.subheader("各運動累積分鐘數")
     if not summary.empty:
        fig = px.bar(
            summary,
            x='exercise_name', # 👈 這裡要對應 GSheet 欄位
            y='minute',        # 👈 這裡要對應 GSheet 欄位
            text='minute',
            color='exercise_name',
            labels={'minute':'累積分鐘數', 'exercise_name':'運動項目'},
            title="您的本月運動分佈圖"
        )
        st.plotly_chart(fig, use_container_width=True)

    # --- 步驟 6: 顯示歷史明細表格 ---
    # --- 步驟 6: 顯示歷史明細表格 ---
     st.divider()
     st.write("歷史運動清單 (包含過往所有紀錄)")
     if 'full_history_df' in locals() and not full_history_df.empty:
        # 🎯 使用未經過濾的資料
        display_df = full_history_df[["date", "exercise_name", "minute"]].copy()
        
        display_df = display_df.rename(columns={
            "date": "日期",
            "exercise_name": "運動項目",
            "minute": "運動時間(分鐘)"
        })
        display_df["日期"] = pd.to_datetime(display_df["日期"]).dt.strftime('%Y-%m-%d')
        st.dataframe(display_df, use_container_width=True, hide_index=True)
     else:
        st.write("目前尚無運動紀錄。")

# ────────────────────── 點數兌換 ──────────────────────
elif st.session_state.view == "點數兌換":
    back_to_home()
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
        # 建議修改點數兌換的輸入框
        wallet_pts = available_points()
        if wallet_pts >= 10:
            points = st.number_input("欲兌換點數", min_value=1, max_value=wallet_pts, step=10, value=min(1, wallet_pts))
            submit = st.form_submit_button("產生兌換條碼", type="primary", use_container_width=True)
        else:
            st.warning("目前點數不足（最低兌換門檻為 1 點）")
            submit = st.form_submit_button("點數不足", disabled=True, use_container_width=True)
            

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


# ────────────────────── 運動場地──────────────────────

elif st.session_state.view == "運動場地":
    back_to_home()
    city_district_selector()
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
                # 建立左右兩欄，左邊顯示資訊，右邊放按鈕
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    st.subheader(f"{p['name']}")
                    st.write(f"{p['address']}")
                
                with col2:
                    
                    map_url = f"https://www.google.com.tw/maps/search/{p['name']}"
                    
                    # 讓按鈕垂直置中（加一點空間）
                    st.write("") 
                    st.link_button(
                        "地圖", 
                        map_url, 
                        use_container_width=True, 
                        type="primary"
                    )
    

# ────────────────────── 活動推廣 ──────────────────────
elif st.session_state.view == "活動推廣":
    back_to_home()
    city_district_selector()
    st.header("近期活動")

    act_city = st.session_state.selected_city
    act_district = st.session_state.selected_district

    # 1. 從 DataFrame 篩選該區域的活動 (確保欄位名稱與 GSheet 一致)
    # 假設 GSheet 欄位為: activity_name, date, time, place, city, district
    mask = (df_activities['city'] == act_city) & (df_activities['district'] == act_district)
    filtered_acts = df_activities[mask].to_dict('records')

    if not filtered_acts:
        st.info(f"目前 {act_city}{act_district} 還沒有活動喔～")
    else:
        st.success(f"顯示 {act_city}{act_district} 的活動")

        for act in filtered_acts:
            with st.container(border=True):
                col1, col2 = st.columns([3, 1])
                with col1:
                    # 顯示你指定的欄位
                    st.subheader(f"{act.get('activity_name', '未命名活動')}")
                    st.write(f"日期：{act.get('date', '-')}　|　⏰ 時間：{act.get('time', '-')}")
                    st.write(f"地點：{act.get('place', '-')}")
                    st.caption(f"地區：{act.get('city')}{act.get('district')}")
                
                with col2:
                    st.write("")
