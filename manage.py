# manage.py
import streamlit as st
import pandas as pd
import datetime
import json
from pathlib import Path
import hashlib

# ====================== 檔案路徑 ======================
USER_FILE = Path("users.json")
PRESCRIPTION_FILE = Path("prescriptions.json")

# ====================== 密碼加密 ======================
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

# ====================== 初始化使用者資料 ======================
if not USER_FILE.exists():
    default_users = {
        "admin": {
            "password": hash_password("123456"),
            "name": "系統管理員",
            "role": "admin",
            "active": True
        },
        "wang": {
            "password": hash_password("wang123"),
            "name": "模擬帳號 個管師",
            "role": "case_manager",
            "active": True  # 預設範例帳號直接啟用
        }
    }
    USER_FILE.write_text(json.dumps(default_users, ensure_ascii=False, indent=2), encoding="utf-8")

# ====================== 登入狀態初始化 ======================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = None
if "user_name" not in st.session_state:
    st.session_state.user_name = None

# ====================== 登出函數 ======================
def logout():
    keys_to_clear = ["logged_in", "username", "user_name", "page", "selected_patient",
                     "patients", "prescriptions"]
    for key in keys_to_clear:
        st.session_state.pop(key, None)
    for key in list(st.session_state.keys()):
        if key.startswith("load_old_"):
            del st.session_state[key]
    st.rerun()

# ====================== 登入頁面 ======================
def login_page():
    st.set_page_config(page_title="個管師登入", page_icon="lock", layout="centered")
    st.markdown("# 運動處方箋系統")
    st.markdown("### 個管師後台登入")

    # 載入使用者資料
    users = json.loads(USER_FILE.read_text(encoding="utf-8"))

    with st.form("登入表單"):
        username = st.text_input("帳號", placeholder="請輸入您的帳號")
        password = st.text_input("密碼", type="password", placeholder="請輸入密碼")
        col1, col2 = st.columns([1, 3])
        with col1:
            login_btn = st.form_submit_button("登入", type="primary", use_container_width=True)

        if login_btn:
            if not username or not password:
                st.error("請輸入帳號與密碼")
            elif username not in users:
                st.error("帳號不存在")
            elif not users[username].get("active", False):
                st.error("此帳號尚未通過管理員審核，請聯繫管理員")
            elif users[username]["password"] == hash_password(password):
                st.session_state.logged_in = True
                st.session_state.username = username
                st.session_state.user_name = users[username]["name"]
                st.success(f"歡迎回來，{users[username]['name']}！")
                st.rerun()
            else:
                st.error("密碼錯誤")
        st.write("測試帳號：wang / 密碼：wang123")

    st.divider()

    # === 帳號申請表單（所有人皆可申請）===
    st.markdown("### 申請新帳號")
    with st.expander("申請個管師帳號（需經管理員審核）", expanded=True):
        with st.form("申請表單"):
            st.info("填寫後送出申請，待管理員審核通過後即可登入")
            new_user = st.text_input("申請帳號（英文/數字）", key="apply_user")
            new_pass = st.text_input("設定密碼", type="password", key="apply_pass")
            new_name = st.text_input("真實姓名（顯示用）", placeholder="例如：張小花 個管師", key="apply_name")
            apply_btn = st.form_submit_button("送出申請", type="secondary")

            if apply_btn:
                if not all([new_user, new_pass, new_name]):
                    st.error("所有欄位皆為必填")
                elif new_user in users:
                    st.error("此帳號已存在或已有人申請")
                else:
                    users[new_user] = {
                        "password": hash_password(new_pass),
                        "name": new_name,
                        "role": "case_manager",
                        "active": False,        # 預設未啟用
                        "applied_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                    }
                    USER_FILE.write_text(json.dumps(users, ensure_ascii=False, indent=2), encoding="utf-8")
                    st.success(f"帳號 {new_user} 申請成功！請等待管理員審核。")
                    st.balloons()

# ====================== admin 專屬：帳號審核頁面 ======================
def admin_approval_page():
    st.header("帳號審核管理")
    users = json.loads(USER_FILE.read_text(encoding="utf-8"))

    pending_users = {k: v for k, v in users.items() if v.get("role") == "case_manager" and not v.get("active", False)}

    if not pending_users:
        st.success("目前沒有待審核的帳號申請")
        return

    st.write(f"共 {len(pending_users)} 筆待審核申請")
    for username, data in pending_users.items():
        with st.expander(f"{username} - {data['name']} （申請時間：{data.get('applied_at', '未知')}）", expanded=False):
            col1, col2 = st.columns([3, 1])
            with col1:
                st.write(f"**姓名：** {data['name']}")
                st.write(f"**申請時間：** {data.get('applied_at', '未知')}")
            with col2:
                if st.button("批准帳號", key=f"approve_{username}", type="primary", use_container_width=True):
                    users[username]["active"] = True
                    del users[username]["applied_at"]  # 清除申請時間
                    USER_FILE.write_text(json.dumps(users, ensure_ascii=False, indent=2), encoding="utf-8")
                    st.success(f"已批准 {username} 的帳號！")
                    st.rerun()
                if st.button("拒絕（刪除）", key=f"reject_{username}", type="secondary"):
                    del users[username]
                    USER_FILE.write_text(json.dumps(users, ensure_ascii=False, indent=2), encoding="utf-8")
                    st.error(f"已拒絕並刪除 {username} 的申請")
                    st.rerun()

# ====================== 主程式：需登入 ======================
if not st.session_state.logged_in:
    login_page()
    st.stop()

# ====================== 已登入：設定頁面 ======================
st.set_page_config(
    page_title="個管師後台 - 運動處方箋系統",
    page_icon="doctor",
    layout="wide",
    initial_sidebar_state="expanded"
)

username = st.session_state.username
user_role = json.loads(USER_FILE.read_text(encoding="utf-8"))[username]["role"]
# ====================== 全域檔案路徑 ======================
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

PATIENTS_FILE = DATA_DIR / "patients.json"
RECORDS_FILE = DATA_DIR / "exercise_records.json"
PRESCRIPTION_FILE = DATA_DIR / "prescriptions.json"

# 確保檔案存在
for f in [PATIENTS_FILE, RECORDS_FILE, PRESCRIPTION_FILE]:
    if not f.exists():
        f.write_text("{}", encoding="utf-8")

# 載入共用資料（放在登入後）
def load_json(file):
    return json.loads(file.read_text(encoding="utf-8"))

def save_json(file, data):
    file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

if st.session_state.logged_in:
    patients_data = load_json(PATIENTS_FILE)
    all_records = load_json(RECORDS_FILE)
    all_prescriptions = load_json(PRESCRIPTION_FILE)
# 載入處方與病人資料（原本邏輯不變）
if "prescriptions" not in st.session_state:
    if PRESCRIPTION_FILE.exists():
        all_prescriptions = json.loads(PRESCRIPTION_FILE.read_text(encoding="utf-8"))
        st.session_state.prescriptions = all_prescriptions.get(username, {})
    else:
        st.session_state.prescriptions = {}

if "patients" not in st.session_state:
    if username == "wang":
        st.session_state.patients = {
            "001": {"name": "陳小美", "gender": "女", "age": 72, "phone": "0912-345-678"},
            "002": {"name": "溫實初", "gender": "男", "age": 78, "phone": "0933-456-789"},
            "003": {"name": "安陵容", "gender": "女", "age": 81, "phone": "0921-567-890"},
            "004": {"name": "余鶯兒", "gender": "女", "age": 75, "phone": "0987-654-321"},
            "005": {"name": "蘇培盛", "gender": "男", "age": 69, "phone": "0918-123-456"},
        }
    else:
        st.session_state.patients = {}

# 其餘病人與處方箋同步邏輯（保持原樣）...
for pid in st.session_state.prescriptions:
    if pid not in st.session_state.patients:
        st.session_state.patients[pid] = {"name": f"未知長輩 {pid}", "gender": "未知", "age": 0, "phone": "未知"}

for pid, history in st.session_state.prescriptions.items():
    if isinstance(history, dict):
        st.session_state.prescriptions[pid] = [history]

# ====================== 側邊欄選單 ======================
with st.sidebar:
    st.title("個管師後台")
    st.write(f"歡迎，**{st.session_state.user_name}**")

    if st.button("登出", type="secondary", use_container_width=True):
        logout()

    st.divider()

    # 一般使用者只有兩個選項
    btn1 = st.button("病人列表", use_container_width=True,
                     type="primary" if st.session_state.get("page", "病人列表") == "病人列表" else "secondary")
    btn2 = st.button("開立／編輯處方箋", use_container_width=True,
                     type="primary" if st.session_state.get("page", "處方箋管理") == "處方箋管理" else "secondary")
    btn3 = st.button("運動回報核可", use_container_width=True,
                     type="primary" if st.session_state.get("page") == "運動核可" else "secondary")
    # admin 額外有審核頁面
    if user_role == "admin":
        
        st.divider()
        st.markdown("### 管理員功能")
        btn4 = st.button("帳號審核管理", use_container_width=True,
                         type="primary" if st.session_state.get("page") == "帳號審核" else "secondary")

    if btn1:
        st.session_state.page = "病人列表"
    if btn2:
        st.session_state.page = "處方箋管理"
    if btn3:
        st.session_state.page = "運動核可"
    if user_role == "admin" and st.session_state.get("page") != "帳號審核":
        if btn3:
            st.session_state.page = "帳號審核"

if "page" not in st.session_state:
    st.session_state.page = "病人列表"

# ====================== 頁面路由 ======================
if st.session_state.page == "病人列表":
    # 【原病人列表程式碼不變】...
    st.header("病人列表")
    
    df = pd.DataFrame.from_dict(st.session_state.patients, orient="index")
    df = df.reset_index().rename(columns={"index": "病歷號"})
    df = df[["病歷號", "name", "gender", "age"]]

    for idx, row in df.iterrows():
        with st.container(border=True):
            col1, col2, col3 = st.columns([3, 2, 2])
            with col1:
                st.write(f"**{row['name']}** ({row['gender']}, {row['age']}歲)")
                st.write(f"病歷號：{row['病歷號']}　")
            with col2:
                pid = row['病歷號']
                if pid in st.session_state.prescriptions:
                    history = st.session_state.prescriptions[pid]
                    if isinstance(history, dict):
                        history = [history]
                    latest = history[-1] if history else {}
                    st.success(latest.get("status", "已開立"))
                else:
                    st.warning("尚未開立處方箋")
            with col3:
                if st.button("前往開立／編輯", key=pid, use_container_width=True):
                    st.session_state.selected_patient = pid
                    st.session_state.page = "處方箋管理"
                    st.rerun()
    # if not st.session_state.patients:
    #     st.info("您目前沒有任何病人資料。請聯繫管理員建立或手動新增。")
    # else:
    #     df = pd.DataFrame.from_dict(st.session_state.patients, orient="index")
    #     df = df.reset_index().rename(columns={"index": "病歷號"})
    #     df = df[["病歷號", "name", "gender", "age", "phone"]]
    #     for idx, row in df.iterrows():
    #         with st.container(border=True):
    #             col1, col2, col3 = st.columns([3, 2, 2])
    #             pid = row['病歷號']
    #             with col1:
    #                 st.write(f"**{row['name']}** ({row['gender']}, {row['age']}歲)")
    #                 st.write(f"病歷號：{pid}")
    #             with col2:
    #                 if pid in st.session_state.prescriptions and st.session_state.prescriptions[pid]:
    #                     latest = st.session_state.prescriptions[pid][-1]
    #                     status = latest.get("status", "已開立")
    #                     if status == "進行中":
    #                         st.success(status)
    #                     elif status == "已完成":
    #                         st.info(status)
    #                     else:
    #                         st.warning(status)
    #                 else:
    #                     st.warning("尚未開立")
    #             with col3:
    #                 if st.button("前往編輯", key=pid, use_container_width=True):
    #                     st.session_state.selected_patient = pid
    #                     st.session_state.page = "處方箋管理"
    #                     st.rerun()
# ====================== 處方箋管理頁面 - 完全修正版 ======================
elif st.session_state.page == "處方箋管理":
    st.header("運動處方箋開立／編輯")

    # 選擇長輩（從全域 patients_data 讀取）
    patient_options = {pid: f"{info['name']} ({pid})" for pid, info in patients_data.items() 
                      if info.get("case_manager") == username or username == "admin"}
    
    if not patient_options:
        st.warning("您目前沒有負責的長者，請先在病人列表新增或由管理員指派。")
        st.stop()

    selected_pid = st.selectbox("選擇長輩", options=list(patient_options.keys()),
                                format_func=lambda x: patient_options[x],
                                index=0 if "selected_patient" not in st.session_state else 
                                      list(patient_options.keys()).index(st.session_state.selected_patient) 
                                      if st.session_state.selected_patient in patient_options else 0)

    st.session_state.selected_patient = selected_pid
    patient = patients_data.get(selected_pid, {})

    st.info(f"目前編輯對象：**{patient.get('name', '未知')}** ({patient.get('gender','?')}, {patient.get('age',0)}歲)　病歷號：{selected_pid}")

    # 讀取這個病人的所有處方紀錄（從全域 all_prescriptions 讀取）
    user_prescriptions = all_prescriptions.get(username, {})
    history = user_prescriptions.get(selected_pid, [])
    if not isinstance(history, list):
        history = [history] if history else []
        user_prescriptions[selected_pid] = history

    # 判斷目前是「新增」還是「編輯舊版」
    editing_index = st.session_state.get(f"editing_index_{selected_pid}", -1)  # -1 = 新增

    if editing_index >= 0 and editing_index < len(history):
        p = history[editing_index]
        is_editing_old = True
        st.warning(f"正在編輯歷史處方：{p['開立日期']} 的版本")
    else:
        p = history[-1] if history else {}
        is_editing_old = False

    # 預設值
    issue_date = datetime.date.today() if not p else datetime.datetime.strptime(p["開立日期"], "%Y-%m-%d").date()
    case_manager = p.get("個管師", st.session_state.user_name) if p else st.session_state.user_name
    contents = "\n".join(p.get("處方內容", [])) if p else ""
    notes = p.get("備註", "") if p else ""
    status = p.get("status", "進行中") if p else "進行中"

    with st.form("處方箋表單"):
        col1, col2 = st.columns(2)
        with col1:
            issue_date = st.date_input("開立日期", value=issue_date)
        with col2:
            case_manager = st.text_input("個管師姓名", value=case_manager)

        contents = st.text_area("處方內容（每行一項）", value=contents, height=200)
        notes = st.text_area("備註或提醒訊息", value=notes, height=100)
        status = st.selectbox("處方狀態", ["進行中", "已完成", "已暫停"], 
                              index=["進行中", "已完成", "已暫停"].index(status))

        col_btn1, col_btn2 = st.columns([1, 4])
        with col_btn1:
            submitted = st.form_submit_button("儲存處方箋", type="primary", use_container_width=True)

        if submitted:
            new_prescription = {
                "開立日期": issue_date.strftime("%Y-%m-%d"),
                "個管師": case_manager,
                "處方內容": [line.strip() for line in contents.split("\n") if line.strip()],
                "備註": notes.strip(),
                "status": status,
                "最後更新": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            }

            # 真正覆蓋或新增
            if is_editing_old:
                history[editing_index] = new_prescription
                st.success(f"已成功修改 {issue_date} 的歷史處方！")
            else:
                # 檢查同一天是否已存在 → 覆蓋（避免重複）
                date_str = issue_date.strftime("%Y-%m-%d")
                found = False
                for i, old in enumerate(history):
                    if old["開立日期"] == date_str:
                        history[i] = new_prescription
                        found = True
                        st.success(f"已更新 {date_str} 的處方")
                        break
                if not found:
                    history.append(new_prescription)
                    st.success(f"已新增處方（{date_str}）")

            # 正確寫回全域資料
            if username not in all_prescriptions:
                all_prescriptions[username] = {}
            all_prescriptions[username][selected_pid] = history

            # 確保病人基本資料存在
            patients_data.setdefault(selected_pid, {}).update({
                "name": patient.get("name", "未知長輩"),
                "gender": patient.get("gender", "未知"),
                "age": patient.get("age", 0),
                "case_manager": username,
            })

            # 一次性儲存兩個檔案
            save_json(PRESCRIPTION_FILE, all_prescriptions)
            save_json(PATIENTS_FILE, patients_data)

            # 清除編輯狀態
            if f"editing_index_{selected_pid}" in st.session_state:
                del st.session_state[f"editing_index_{selected_pid}"]

            st.balloons()
            st.rerun()

    # === 歷史處方顯示 + 真正可編輯 ===
    if history:
        st.divider()
        st.subheader("歷史處方紀錄")
        for idx, p in enumerate(reversed(history)):
            actual_idx = len(history) - 1 - idx
            with st.expander(f"{p['開立日期']} ｜ {p['個管師']} ｜ {p.get('status','進行中')}", expanded=(actual_idx == len(history)-1)):
                col1, col2 = st.columns([1, 5])
                with col1:
                    s = p.get("status", "進行中")
                    if s == "進行中": st.success("進行中")
                    elif s == "已完成": st.info("已完成")
                    else: st.warning(s)
                with col2:
                    st.caption(f"最後更新：{p.get('最後更新', '無')}")

                st.markdown("### 處方內容")
                for item in p.get("處方內容", []):
                    st.markdown(f"• {item}")
                if p.get("備註"):
                    st.caption(f"備註：{p['備註']}")

                col_a, col_b = st.columns(2)
                with col_a:
                    if st.button("編輯此版本", key=f"edit_{selected_pid}_{actual_idx}"):
                        st.session_state[f"editing_index_{selected_pid}"] = actual_idx
                        st.rerun()
                with col_b:
                    if st.button("刪除此版本", key=f"delete_{selected_pid}_{actual_idx}", type="secondary"):
                        if st.session_state.get("confirm_delete") == f"{selected_pid}_{actual_idx}":
                            history.pop(actual_idx)
                            all_prescriptions[username][selected_pid] = history
                            save_json(PRESCRIPTION_FILE, all_prescriptions)
                            st.success("已刪除")
                            del st.session_state["confirm_delete"]
                            st.rerun()
                        else:
                            st.session_state.confirm_delete = f"{selected_pid}_{actual_idx}"
                            st.warning("再次點擊確認刪除")



elif st.session_state.page == "帳號審核" and user_role == "admin":
    admin_approval_page()
elif st.session_state.page == "運動核可":
    st.header("長者運動回報核可")

    # 選擇病人
    patient_options = {pid: f"{info['name']} ({pid})" for pid, info in patients_data.items() 
                      if info.get("case_manager") == username}
    
    if not patient_options:
        st.warning("您目前沒有負責的長者")
        st.stop()

    selected_pid = st.selectbox("選擇長者", options=list(patient_options.keys()),
                                format_func=lambda x: patient_options[x])

    records = all_records.get(selected_pid, [])
    if not records:
        st.info("這位長者還沒有運動紀錄")
    else:
        pending = [r for r in records if not r.get("approved", False)]
        st.metric("待核可筆數", len(pending))

        for record in records:
            approved = record.get("approved", False)
            with st.container(border=True):
                col1, col2, col3 = st.columns([3, 2, 2])
                with col1:
                    status = "已核可" if approved else "待核可"
                    color = "green" if approved else "orange"
                    st.markdown(f"**{record['date']}**　{record['exercise']}　{record['minutes']} 分鐘　→　{record['points_base']} 點")
                    st.markdown(f"<span style='color:{color}'>● {status}</span>", unsafe_allow_html=True)
                with col2:
                    st.write(f"已發放：{record['points_auto']} 點（60%）")
                    if not approved:
                        st.write(f"待補發：{record['points_pending']} 點（40%）")
                    else:
                        st.write(f"已補發：{record['points_pending']} 點")
                with col3:
                    if not approved:
                        if st.button("核可發放", key=f"approve_{selected_pid}_{record['date']}_{record['exercise']}"):
                            # 執行核可
                            record["approved"] = True
                            record["approved_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                            
                            # 更新病人點數
                            patients_data[selected_pid]["total_points_pending"] -= record['points_pending']
                            patients_data[selected_pid]["total_points_approved"] += record['points_pending']
                            patients_data[selected_pid]["case_manager"] = username
                            save_json(RECORDS_FILE, all_records)
                            save_json(PATIENTS_FILE, patients_data)
                            st.success(f"已核可補發 {record['points_pending']} 點！")
                            st.rerun()
                    else:
                        st.success("已核可")