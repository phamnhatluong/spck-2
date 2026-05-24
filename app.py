import streamlit as st
import pandas as pd
import plotly.express as px
from sklearn.linear_model import LinearRegression
import numpy as np
import datetime
import sqlite3

# --- CẤU HÌNH TRANG WEB ---
st.set_page_config(page_title="Hệ Thống Dự Báo Ngành Lịch Sử", layout="wide")

DB_FILE = "industry_data.db"

# --- CÁC HÀM XỬ LÝ CƠ SỞ DỮ LIỆU (SQLITE) ---
def init_db():
    """Khởi tạo cấu trúc file lưu trữ nếu chưa tồn tại"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    # Bảng quản lý danh mục ngành và thời gian cập nhật
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS industry_registry (
            industry_name TEXT PRIMARY KEY,
            last_updated TEXT
        )
    ''')
    conn.commit()
    conn.close()

def save_to_db(df, industry_name):
    """Lưu dataframe của một ngành vào cơ sở dữ liệu"""
    conn = sqlite3.connect(DB_FILE)
    # Thêm cột thời gian hệ thống ghi nhận để theo dõi lịch sử thay đổi
    df_to_save = df.copy()
    # Chuyển đổi các cột datetime sang chuỗi để lưu vào SQL tốt hơn
    for col in df_to_save.columns:
        if pd.api.types.is_datetime64_any_dtype(df_to_save[col]):
            df_to_save[col] = df_to_save[col].dt.strftime('%Y-%m-%d')
            
    df_to_save['system_upload_time'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Lưu toàn bộ bảng dữ liệu thô (nếu trùng tên ngành sẽ ghi đè/cập nhật phiên bản mới nhất)
    # Tên bảng trong DB chính là tên ngành (xóa khoảng trắng và ký tự đặc biệt để tránh lỗi SQL)
    table_name = "".join(x for x in industry_name if x.isalnum())
    df_to_save.to_sql(table_name, conn, if_exists='replace', index=False)
    
    # Cập nhật thông tin vào bảng đăng ký chung
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO industry_registry (industry_name, last_updated)
        VALUES (?, ?)
    ''', (industry_name, datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    
    conn.commit()
    conn.close()

def get_public_industries():
    """Lấy danh sách các ngành đã lưu trong file"""
    conn = sqlite3.connect(DB_FILE)
    try:
        df_registry = pd.read_sql_query("SELECT * FROM industry_registry", conn)
        conn.close()
        return df_registry
    except:
        conn.close()
        return pd.DataFrame(columns=['industry_name', 'last_updated'])

def load_from_db(industry_name):
    """Tải dữ liệu của một ngành cụ thể ra"""
    conn = sqlite3.connect(DB_FILE)
    table_name = "".join(x for x in industry_name if x.isalnum())
    df_loaded = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
    conn.close()
    return df_loaded

# Khởi chạy DB khi mở web
init_db()

# --- GIAO DIỆN CHÍNH ---
st.title("📈 Hệ Thống Phân Tích & Quản Lý Lịch Sử Biến Động Ngành")
st.write("Dữ liệu sau khi chia sẻ công khai sẽ được lưu vĩnh viễn vào hệ thống để mọi người dùng đều có thể theo dõi sự thay đổi.")

# --- TẢI FILE / CHỌN FILE ---
tabs = st.tabs(["📁 Tải dữ liệu mới", "🌐 Lịch sử các ngành trên hệ thống"])
df = None
file_label = ""

with tabs[0]:
    uploaded_file = st.file_uploader("Chọn file CSV/XLSX dữ liệu ngành", type=["csv", "xlsx"])
    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)
            # Thử tự lấy tên ngành từ cột 'industry' nếu có, không thì lấy tên file
            if 'industry' in df.columns and df['industry'].notna().any():
                file_label = str(df['industry'].dropna().iloc[0])
            else:
                file_label = uploaded_file.name.split('.')[0]
            st.success(f"⚡ Đã đọc dữ liệu ngành: {file_label}")
        except Exception as e:
            st.error(f"Lỗi đọc file: {e}")

with tabs[1]:
    df_registry = get_public_industries()
    if not df_registry.empty:
        st.write("### 📜 Danh sách các ngành đã từng tải lên và thời gian cập nhật:")
        # Hiển thị bảng danh mục lịch sử
        st.dataframe(df_registry, use_container_width=True)
        
        selected_public = st.selectbox("Chọn ngành từ hệ thống để xem và so sánh:", df_registry['industry_name'].tolist())
        if selected_public:
            df = load_from_db(selected_public)
            file_label = selected_public
            st.info(f"Đang hiển thị dữ liệu lịch sử lưu trữ của ngành: **{file_label}**")
    else:
        st.write("ℹ️ Chưa có ngành nào được lưu công khai vào file hệ thống.")

# --- XỬ LÝ DỮ LIỆU TỰ ĐỘNG THÍCH NGHI ---
if df is not None:
    all_columns = list(df.columns)
    
    # Tự động tìm cột thời gian và cột số giống phiên bản trước
    date_col = None
    for col in all_columns:
        if any(keyword in str(col).lower() for keyword in ['date', 'ngày', 'time', 'tháng', 'year', 'thời gian']):
            try:
                df[col] = pd.to_datetime(df[col], errors='coerce')
                if df[col].notna().sum() > 0:
                    date_col = col
                    break
            except:
                pass
                
    numeric_cols = []
    for col in all_columns:
        if col != date_col and col != 'system_upload_time':
            converted = pd.to_numeric(df[col], errors='coerce')
            if converted.notna().sum() / len(df) > 0.5:
                df[col] = converted
                numeric_cols.append(col)

    categorical_cols = [col for col in all_columns if col not in numeric_cols and col != date_col and col != 'system_upload_time']

    # Thanh Sidebar điều chỉnh nhanh
    with st.sidebar:
        st.header("⚙️ Cấu Hình Mô Hình")
        user_date_col = st.selectbox("Cột Thời gian (Trục X):", [None] + all_columns, index=all_columns.index(date_col) if date_col in all_columns else 0)
        user_target_col = st.selectbox("Chỉ số cần dự báo (Trục Y):", numeric_cols if numeric_cols else all_columns, index=0)
        user_cat_col = st.selectbox("Phân loại chính:", categorical_cols if categorical_cols else all_columns, index=0)

    if user_date_col and user_date_col in df.columns:
        df[user_date_col] = pd.to_datetime(df[user_date_col], errors='coerce')

    # Hiển thị dữ liệu
    st.markdown("---")
    st.subheader(f"📊 Kết quả phân tích ngành: {file_label.upper()}")
    
    with st.expander("🔍 Xem bảng dữ liệu chi tiết"):
        st.dataframe(df)

    # Thống kê nhanh
    if numeric_cols:
        st.write("### 📌 Trung bình các chỉ số hiện tại:")
        metric_cols_layout = st.columns(min(len(numeric_cols), 4))
        for idx, col_num in enumerate(numeric_cols[:4]):
            with metric_cols_layout[idx]:
                avg_val = df[col_num].mean()
                st.metric(f"{col_num}", f"{avg_val:,.2f}" if avg_val < 1000 else f"{avg_val:,.0f}")

    # Thuật toán dự báo tương lai
    if user_date_col and user_target_col and df[user_date_col].notna().sum() > 1:
        try:
            df_trend = df.groupby(user_date_col)[user_target_col].sum().reset_index().dropna()
            min_date = df_trend[user_date_col].min()
            df_trend['date_delta'] = (df_trend[user_date_col] - min_date).dt.days
            
            X = df_trend[['date_delta']]
            y = df_trend[user_target_col]
            
            model = LinearRegression()
            model.fit(X, y)
            
            last_date = df_trend[user_date_col].max()
            future_dates = [last_date + datetime.timedelta(days=int(x)) for x in range(30, 395, 30)]
            future_deltas = [(d - min_date).days for d in future_dates]
            y_pred = model.predict(np.array(future_deltas).reshape(-1, 1))
            
            df_future = pd.DataFrame({user_date_col: future_dates, user_target_col: y_pred, 'Trạng thái': 'Dự báo tương lai'})
            df_trend['Trạng thái'] = 'Dữ liệu lịch sử gốc'
            df_total = pd.concat([df_trend[[user_date_col, user_target_col, 'Trạng thái']], df_future])
            
            fig_forecast = px.line(df_total, x=user_date_col, y=user_target_col, color='Trạng thái', title=f"Xu Hướng Dự Báo Chỉ Số '{user_target_col}'")
            st.plotly_chart(fig_forecast, use_container_width=True)
            
            # Đề xuất chiến lược
            st.subheader("💡 Nhận Định Chiến Lược")
            y_last = df_trend[user_target_col].iloc[-1]
            growth_rate = (y_pred[-1] - y_last) / y_last if y_last != 0 else 0
            if growth_rate > 0.05:
                st.success(f"📈 **Xu hướng phát triển tốt:** Dự kiến `{user_target_col}` sẽ tăng thêm {growth_rate*100:.1f}% dựa trên quy luật từ các dữ liệu đã tải lên trước đó.")
            elif growth_rate < -0.05:
                st.error(f"📉 **Cảnh báo suy giảm:** Xu hướng dự báo giảm {abs(growth_rate)*100:.1f}%. Cần chuẩn bị phương án dự phòng chi phí.")
            else:
                st.warning(f"🔄 **Trạng thái bình ổn:** Chỉ số biến động nhẹ ({growth_rate*100:.1f}%), thị trường đang đi vào giai đoạn ổn định ổn định.")
        except Exception as e:
            st.info(f"Chưa đủ dữ liệu chuỗi thời gian để chạy thuật toán AI dự báo ({e}).")

    # Tùy biến biểu đồ theo ý muốn
    st.subheader("🎨 Thiết Kế Biểu Đồ Thống Kê")
    col_chart1, col_chart2 = st.columns([1, 3])
    with col_chart1:
        chart_type = st.selectbox("Dạng biểu đồ:", ["Cột (Bar Chart)", "Đường (Line Chart)", "Tròn (Pie Chart)", "Phân tán (Scatter Chart)"])
        x_axis = st.selectbox("Trục X:", all_columns, index=all_columns.index(user_cat_col) if user_cat_col in all_columns else 0)
        y_axis = st.selectbox("Trục Y:", numeric_cols if numeric_cols else all_columns, index=0)
        color_by = st.selectbox("Phân loại màu:", [None] + all_columns)

    with col_chart2:
        try:
            if chart_type == "Cột (Bar Chart)":
                fig = px.bar(df, x=x_axis, y=y_axis, color=color_by, title=f"Biểu đồ {y_axis} theo {x_axis}")
            elif chart_type == "Đường (Line Chart)":
                fig = px.line(df, x=x_axis, y=y_axis, color=color_by, title=f"Biểu đồ đường {y_axis}")
            elif chart_type == "Tròn (Pie Chart)":
                df_pie = df.groupby(x_axis)[y_axis].sum().reset_index()
                fig = px.pie(df_pie, names=x_axis, values=y_axis, title=f"Tỷ lệ {y_axis}")
            elif chart_type == "Phân tán (Scatter Chart)":
                fig = px.scatter(df, x=x_axis, y=y_axis, color=color_by, title=f"Mối tương quan {x_axis} và {y_axis}")
            st.plotly_chart(fig, use_container_width=True)
        except Exception as e:
            st.error(f"Lỗi vẽ biểu đồ: {e}")

    # --- CHIA SẺ CÔNG KHAI VÀ GHI VÀO FILE RIÊNG BIỆT ---
    st.markdown("---")
    st.subheader("💾 Lưu trữ vĩnh viễn vào hệ thống")
    share_choice = st.radio("Bạn có muốn lưu/cập nhật dữ liệu ngành này vào tệp lưu trữ chung không?", 
                            ("🔒 Không, chỉ xem tạm thời", "🌐 Có, lưu vào hệ thống chung để theo dõi lâu dài"))
    
    if st.button("Xác nhận thực hiện lưu tệp"):
        if share_choice == "🌐 Có, lưu vào hệ thống chung để theo dõi lâu dài":
            save_to_db(df, file_label)
            st.success(f"🎉 Đã lưu trữ thành công dữ liệu ngành '{file_label}' vào cơ sở dữ liệu `industry_data.db`! Hãy tải lại trang để thấy cập nhật ở Tab công khai.")
        else:
            st.info("Dữ liệu chỉ hiển thị trong phiên này và không ghi vào tệp.")