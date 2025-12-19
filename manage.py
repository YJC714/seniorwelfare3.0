import streamlit as st
import pandas as pd
import datetime
from streamlit_gsheets import GSheetsConnection

# ====================== 1. 頁面設定 ======================
st.set_page_config(page_title="個管師後台 - 李佳芬個管師", layout="wide")
CASE_MANAGER_NAME = "李佳芬個管師"

# 定義 CFS 與運動建議的對應關係
FRAILTY_LOGIC = {
    "第1級非常健康": {"value": 1.0, "suggested": ["步行", "重量訓練", "快走", "舉寶特瓶"]},
    "第2級很好": {"value": 2.0, "suggested": ["步行", "慢跑", "社交舞", "太極拳"]},
    "第3級還可以": {"value": 3.0, "suggested": ["步行", "起立坐下訓練", "平衡練習", "伸展運動"]},
    "第4級脆弱": {"value": 4.0, "suggested": ["步行", "手臂向上拉伸", "抬腳練習", "伸展運動"]},
    "第5級輕度衰弱": {"value": 5.0, "suggested": ["抬腳練習", "舉寶特瓶", "擴胸運動", "手部握力練習"]}
}

# ====================== 2. GSheet 連線 ======================
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    df_patients = conn.read(worksheet="patients", ttl=2)
    df_prescriptions = conn.read(worksheet="prescriptions", ttl=2)
    df_exercise = conn.read(worksheet="exercise_report", ttl=2)
    return df_patients, df_prescriptions, df_exercise

df_p, df_pres, df_ex = load_data()

# ====================== 3. 頁面切換邏輯 ======================
if "page" not in st.session_state:
    st.session_state.page = "病人列表"

with st.sidebar:
    st.title("個管師後台")
    st.write(f"歡迎，**{CASE_MANAGER_NAME}**")
    st.divider()
    if st.button("病人列表", use_container_width=True): 
        st.session_state.page = "病人列表"
        st.rerun()
    if st.button("開立處方箋", use_container_width=True): 
        st.session_state.page = "處方箋管理"
        st.rerun()
    if st.button("運動回報核可", use_container_width=True): 
        st.session_state.page = "運動回報核可"
        st.rerun()

# ====================== 4. 病人列表 ======================
if st.session_state.page == "病人列表":
    st.header("病人列表")
    my_patients = df_p[df_p['case_manager'] == CASE_MANAGER_NAME]
    
    for _, row in my_patients.iterrows():
        pid = str(row['patient_num'])
        patient_pres = df_pres[df_pres['patient_num'].astype(str) == pid]
        
        with st.container(border=True):
            c1, c2, c3 = st.columns([2, 2, 1])
            with c1:
                st.subheader(f"{row['name']}")
                st.write(f"病歷號：{pid} | 年齡：{int(row['age'])} 歲")
            with c2:
                if not patient_pres.empty:
                    latest = patient_pres.iloc[-1]
                    f_val = latest.get('frailty', '-')
                    st.success(f"處方狀態：{latest['status']}")
                else:
                    st.warning("狀態：尚未開立處方箋")
            with c3:
                if st.button("詳情 / 編輯", key=f"edit_{pid}", use_container_width=True):
                    st.session_state.selected_pid = pid
                    st.session_state.page = "處方箋管理"
                    st.rerun()

# ====================== 5. 處方箋管理 ======================
elif st.session_state.page == "處方箋管理":
    target_pid = st.session_state.get("selected_pid", "1.0")
    p_info = df_p[df_p['patient_num'].astype(str) == target_pid].iloc[0]

    st.header(f"運動處方箋管理：{p_info['name']}")

    patient_history = df_pres[df_pres['patient_num'].astype(str) == target_pid].sort_values(by="prescription_date", ascending=False)

    with st.form("prescription_form"):
        st.subheader("新增處方箋")
        col1, col2 = st.columns(2)
        
        with col1:
            selected_f_label = st.selectbox("臨床衰弱量表 (CFS) 評估", options=list(FRAILTY_LOGIC.keys()))
            f_data = FRAILTY_LOGIC[selected_f_label]
            st.info(f"針對{selected_f_label}，建議運動：{', '.join(f_data['suggested'])}")
            
            selected_ex = st.multiselect("選擇運動項目", 
                                        options=f_data['suggested'] + ["其他"], 
                                        default=[f_data['suggested'][0]])
            other_ex = st.text_input("輸入其他運動項目 (若有選擇'其他')")
            
        with col2:
            freq = st.number_input("每週頻率 (次)", min_value=1, max_value=7, value=3)
            duration = st.number_input("每次時長 (分鐘)", min_value=5, max_value=120, value=30, step=5)
            status = st.selectbox("處方狀態", ["進行中", "已完成", "調整中"])
            notes = st.text_area("備註 (長輩特殊狀況)", height=100)

        if st.form_submit_button("儲存並發布新處方箋", use_container_width=True):
            final_items = [i for i in selected_ex if i != "其他"]
            if "其他" in selected_ex and other_ex:
                final_items.append(other_ex.strip())
            
            new_data = {
                "case_manager": CASE_MANAGER_NAME,
                "patient_num": target_pid,
                "prescription_date": datetime.date.today().strftime("%Y-%m-%d"),
                "case_manager_name": "李佳芬",
                "content": "、".join(final_items),
                "minute": int(duration),
                "frequency": int(freq),
                "other": notes,
                "status": status,
                "frailty": f_data["value"],
                "last_update": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            }
            st.success(f"已儲存！衰弱等級：{f_data['value']} | 項目：{new_data['content']}")

    st.divider()
    st.subheader("歷史處方紀錄")
    if patient_history.empty:
        st.write("目前尚無歷史紀錄。")
    else:
        for idx, h_row in patient_history.iterrows():
            with st.expander(f"{h_row['prescription_date']} | 狀態：{h_row['status']}"):
                if ( h_row['frequency']=='0' and h_row['minute']=='0'):
                    st.write(f"運動處方箋： {h_row['content']}")
                    st.caption(f"備註：{h_row.get('other', '無')}")
                else:
                    st.write(f"運動處方箋： {h_row['content']}")
                    st.write(f"計畫： 每週 {h_row['frequency']} 次，每次 {h_row['minute']} 分鐘")
                    st.caption(f"備註：{h_row.get('other', '無')}")

# ====================== 6. 運動回報核可 ======================
elif st.session_state.page == "運動回報核可":
    st.header("運動回報核可")

    # 1. 篩選 Jiafen 旗下的長者
    my_patients_df = df_p[df_p['case_manager'] == CASE_MANAGER_NAME]
    patient_options = {row['name']: str(row['patient_num']) for _, row in my_patients_df.iterrows()}
    selected_p_name = st.selectbox("選擇長者", options=["全部"] + list(patient_options.keys()))

    # 2. 獲取 12 月的所有紀錄 (移除原本的 approved != 'TRUE' 過濾)
    df_ex['date'] = pd.to_datetime(df_ex['date'])
    december_logs = df_ex[(df_ex['date'].dt.month == 12) & (df_ex['date'].dt.year == 2025)]

    if selected_p_name != "全部":
        target_pid = patient_options[selected_p_name]
        final_logs = december_logs[december_logs['patient_num'].astype(str) == target_pid]
    else:
        target_pids = list(patient_options.values())
        final_logs = december_logs[december_logs['patient_num'].astype(str).isin(target_pids)]

    if final_logs.empty:
        st.info("目前沒有 12 月的運動回報紀錄。")
    else:
        # 按日期排序，最新的在前
        final_logs = final_logs.sort_values(by='date', ascending=False)
        
        for idx, log in final_logs.iterrows():
            pid = str(log['patient_num'])
            current_p_name = df_p[df_p['patient_num'].astype(str) == pid]['name'].values[0]
            
            # 判斷當前這筆紀錄在資料庫中是否已核可
            is_already_approved = str(log['approved']).upper() == 'TRUE'
            
            # --- 比對處方箋邏輯 ---
            latest_pres = df_pres[(df_pres['patient_num'].astype(str) == pid) & 
                                 (df_pres['status'] == "進行中")].sort_values(by="prescription_date").iloc[-1:]
            
            is_valid_exercise = False
            if not latest_pres.empty:
                pres_content = latest_pres['content'].values[0]
                if log['exercise_name'] in pres_content:
                    is_valid_exercise = True

            # --- 顯示介面 ---
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([1.5, 2, 2, 1])
                with c1:
                    st.write(f"姓名：{current_p_name}")
                    st.caption(f"ID: {pid}")
                with c2:
                    st.write(f"日期：{log['date'].strftime('%Y-%m-%d')}")
                    st.write(f"回報項目：{log['exercise_name']}")
                with c3:
                    duration = int(log['minute'])
                    bonus_pts = int(duration / 4 * 6)
                    st.write(f"運動時長：{duration} 分鐘")
                    st.write(f"預計獎勵：{bonus_pts} 點")
                
                with c4:
                    if is_already_approved:
                        # 狀態 A：已經核可過的項目，永久顯示綠色成功狀態
                        st.success("已核可")
                    elif is_valid_exercise:
                        # 狀態 B：符合處方但尚未核可
                        if st.button("核可", key=f"btn_{idx}", use_container_width=True):
                            # A. 更新運動紀錄表 (將該行 approved 設為 True)
                            df_ex.at[idx, 'approved'] = True
                            conn.update(worksheet="exercise_report", data=df_ex)
                            
                            # B. 更新病人點數表
                            p_idx = df_p[df_p['patient_num'].astype(str) == pid].index[0]
                            current_pending = df_p.at[p_idx, 'total_points_pending']
                            new_pending = (0 if pd.isna(current_pending) else current_pending) + bonus_pts
                            df_p.at[p_idx, 'total_points_pending'] = new_pending
                            
                            conn.update(worksheet="patients", data=df_p)
                            
                            st.rerun() # 重新整理後，這筆紀錄會因為 is_already_approved 變成 True 而顯示成功標籤
                    else:
                        # 狀態 C：不符合處方
                        st.error("額外運動")









