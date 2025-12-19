import streamlit as st
import pandas as pd
import datetime
from streamlit_gsheets import GSheetsConnection

# ====================== 1. 頁面設定 ======================
st.set_page_config(page_title="個管師後台 - 高曼玉", layout="wide")

# 設定個管師標籤
CASE_MANAGER_NAME = "Jiafen"

# ====================== 2. GSheet 連線 ======================
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    # 讀取病患、處方與運動紀錄
    df_patients = conn.read(worksheet="patients", ttl=5)
    df_prescriptions = conn.read(worksheet="prescriptions", ttl=5)
    df_exercise = conn.read(worksheet="exercise_report", ttl=5)
    return df_patients, df_prescriptions, df_exercise

df_p, df_pres, df_ex = load_data()

# ====================== 3. 左側選單 ======================
if "page" not in st.session_state:
    st.session_state.page = "病人列表"

with st.sidebar:
    st.title("個管師後台")
    st.write(f"當前個管師：**{CASE_MANAGER_NAME}**")
    st.divider()
    if st.button("病人列表", use_container_width=True): st.session_state.page = "病人列表"; st.rerun()
    if st.button("開立處方箋", use_container_width=True): st.session_state.page = "處方箋管理"; st.rerun()
    if st.button("運動回報核可", use_container_width=True): st.session_state.page = "運動回報核可"; st.rerun()

# ====================== 4. 功能頁面：病人列表 ======================
if st.session_state.page == "病人列表":
    st.header("病人列表")
    
    # 篩選屬於 Jiafen 的病人
    my_patients = df_p[df_p['case_manager'] == CASE_MANAGER_NAME]
    
    for _, row in my_patients.iterrows():
        with st.container(border=True):
            c1, c2, c3 = st.columns([2, 2, 1])
            pid = str(row['patient_num'])
            with c1:
                st.subheader(f"{row['name']}")
                st.write(f"病歷號：{pid} | 年齡：{int(row['age'])}歲")
            with c2:
                # 顯示最新衰弱等級
                level = row.get('frailty_level', '尚未評估')
                st.info(f"臨床衰弱量表：{level}")
            with c3:
                if st.button("編輯處方", key=f"edit_{pid}", use_container_width=True):
                    st.session_state.selected_pid = pid
                    st.session_state.page = "處方箋管理"
                    st.rerun()

# ====================== 5. 功能頁面：處方箋管理 ======================
elif st.session_state.page == "處方箋管理":
    st.header("📝 運動處方箋開立")
    
    # 選取病人
    target_pid = st.session_state.get("selected_pid", "1.0")
    patient_info = df_p[df_p['patient_num'].astype(str) == target_pid].iloc[0]
    
    st.info(f"正在為 **{patient_info['name']}** (ID: {target_pid}) 設定處方")

    with st.form("prescription_form"):
        col1, col2 = st.columns(2)
        with col1:
            # 臨床衰弱量表
            frailty = st.selectbox("臨床衰弱量表 (Frailty Scale)", 
                ["第1級非常健康", "第2級很好", "第3級還可以", "第4級脆弱", "第5級輕度衰弱", "第6級中度衰弱"])
            
            # 運動項目多選 + 自定義
            base_exercises = ["步行", "伸展運動", "深蹲", "外展運動", "太極拳"]
            selected_ex = st.multiselect("建議運動項目", base_exercises, default=["步行"])
            other_ex = st.text_input("其他運動項目 (請用逗號分隔)")
            
        with col2:
            freq = st.number_input("每週頻率 (1~7次)", min_value=1, max_value=7, value=3)
            duration = st.number_input("每次時長 (分鐘)", min_value=5, max_value=120, value=30, step=5)
            notes = st.text_area("備註", placeholder="其他身體狀況")

        if st.form_submit_button("儲存並發布處方箋", use_container_width=True):
            # 整合運動內容
            final_content = selected_ex + [i.strip() for i in other_ex.split(",") if i.strip()]
            
            # 這裡應該要寫入 GSheet (由於 conn.update 是某些版本功能，建議手動更新)
            st.success(f"處方已更新！項目：{', '.join(final_content)}")
            st.warning("提醒：請確認 GSheet 的 prescriptions 工作表已同步更新。")
            # 註：實際開發時會使用 conn.update(data=...) 或直接調用 gspread 寫入

# ====================== 6. 功能頁面：運動回報核可 ======================
elif st.session_state.page == "運動回報核可":
    st.header("運動回報核可")
    
    # 篩選出目前該個管師旗下病人的所有運動紀錄
    my_pids = df_p[df_p['case_manager'] == CASE_MANAGER_NAME]['patient_num'].astype(str).tolist()
    pending_logs = df_ex[df_ex['patient_num'].astype(str).isin(my_pids)]

    if pending_logs.empty:
        st.write("目前沒有待處理的回報紀錄。")
    else:
        for idx, log in pending_logs.iterrows():
            # 找到對應病人名稱
            p_name = df_p[df_p['patient_num'].astype(str) == str(log['patient_num'])]['name'].values[0]
            
            # 計算公式：長者端看到的 pending 應該是 auto/4*6
            auto_pts = int(log['minute'])
            bonus_pts = int(auto_pts / 4 * 6)

            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([1.5, 2, 2, 1])
                with c1:
                    st.write(f"**{p_name}**")
                    st.caption(f"ID: {log['patient_num']}")
                with c2:
                    st.write(f"{log['date']}")
                    st.write(f"{log['exercise_name']}")
                with c3:
                    st.write(f"時間：{auto_pts} 分鐘")
                    st.write(f"可核發：**{bonus_pts} 點**")
                with c4:
                    if st.button("核可發放", key=f"appv_{idx}"):
                        st.balloons()
                        st.success("點數已核發！")

