import sqlite3
import uuid
import json
from datetime import datetime, date
from pathlib import Path

import pandas as pd
import streamlit as st

# =========================
# 1. CẤU HÌNH ỨNG DỤNG
# =========================

APP_DIR = Path(__file__).parent
DB_PATH = APP_DIR / "orders.db"

st.set_page_config(
    page_title="Bếp Nhà - Tính hóa đơn",
    page_icon="🍜",
    layout="wide"
)

# =========================
# 2. GIAO DIỆN
# =========================

st.markdown("""
<style>
    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
        max-width: 1400px;
    }

    .hero {
        padding: 25px;
        border-radius: 18px;
        background: linear-gradient(120deg, #173f35, #28745b);
        color: white;
        margin-bottom: 25px;
    }

    .hero h1 {
        color: white;
        margin: 0;
    }

    .hero p {
        color: #e4f4eb;
        margin-top: 8px;
    }

    div[data-testid="stMetric"] {
        background: #f7faf8;
        border: 1px solid #e4eee8;
        padding: 14px;
        border-radius: 14px;
    }

    [data-testid="stSidebar"] {
        background: #f6faf7;
    }
</style>

<div class="hero">
    <h1>🍜 BẾP NHÀ</h1>
    <p>Quản lý món ăn · Tạo hóa đơn · Theo dõi doanh thu</p>
</div>
""", unsafe_allow_html=True)


# =========================
# 3. KẾT NỐI CƠ SỞ DỮ LIỆU
# =========================

def connect_db():
    conn = sqlite3.connect(
        DB_PATH,
        check_same_thread=False
    )
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with connect_db() as conn:

        conn.execute("""
            CREATE TABLE IF NOT EXISTS menu (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                category TEXT NOT NULL,
                price INTEGER NOT NULL CHECK(price >= 0),
                active INTEGER NOT NULL DEFAULT 1
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_code TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                customer_name TEXT,
                payment_method TEXT NOT NULL,
                subtotal INTEGER NOT NULL,
                discount_amount INTEGER NOT NULL,
                vat_rate REAL NOT NULL,
                vat_amount INTEGER NOT NULL,
                total INTEGER NOT NULL,
                cash_received INTEGER NOT NULL,
                change_amount INTEGER NOT NULL,
                items_json TEXT NOT NULL
            )
        """)

        # Tạo menu mẫu khi chưa có dữ liệu
        count = conn.execute(
            "SELECT COUNT(*) FROM menu"
        ).fetchone()[0]

        if count == 0:
            sample_menu = [
                ("Cơm sườn nướng", "Món chính", 45000, 1),
                ("Cơm gà chiên nước mắm", "Món chính", 42000, 1),
                ("Phở bò", "Món chính", 50000, 1),
                ("Bún thịt nướng", "Món chính", 40000, 1),
                ("Gỏi cuốn (2 cuốn)", "Món ăn vặt", 25000, 1),
                ("Khoai tây chiên", "Món ăn vặt", 30000, 1),
                ("Trà đá", "Đồ uống", 5000, 1),
                ("Trà chanh", "Đồ uống", 18000, 1),
                ("Cà phê sữa", "Đồ uống", 22000, 1),
                ("Nước suối", "Đồ uống", 10000, 1),
            ]

            conn.executemany("""
                INSERT INTO menu (name, category, price, active)
                VALUES (?, ?, ?, ?)
            """, sample_menu)


init_db()


# =========================
# 4. CÁC HÀM HỖ TRỢ
# =========================

def money(value):
    """Định dạng tiền Việt Nam."""
    return f"{int(value):,}".replace(",", ".") + " đ"


def get_menu(active_only=True):
    with connect_db() as conn:
        query = """
            SELECT id, name, category, price, active
            FROM menu
        """

        if active_only:
            query += " WHERE active = 1"

        query += " ORDER BY category, name"

        return pd.read_sql_query(query, conn)


def get_orders():
    with connect_db() as conn:
        return pd.read_sql_query(
            "SELECT * FROM orders ORDER BY created_at DESC",
            conn
        )


# Khởi tạo giỏ hàng
if "cart" not in st.session_state:
    st.session_state.cart = {}

if "last_invoice" not in st.session_state:
    st.session_state.last_invoice = None


# =========================
# 5. THANH ĐIỀU HƯỚNG
# =========================

page = st.sidebar.radio(
    "ĐIỀU HƯỚNG",
    [
        "🧾 Tạo hóa đơn",
        "🍽️ Quản lý món ăn",
        "📊 Lịch sử & thống kê"
    ]
)

st.sidebar.divider()
st.sidebar.caption("Ứng dụng Python + Streamlit")
st.sidebar.caption("Dữ liệu được lưu bằng SQLite.")


# ==================================================
# 6. CHỨC NĂNG TẠO HÓA ĐƠN
# ==================================================

if page == "🧾 Tạo hóa đơn":

    menu_df = get_menu()

    left, right = st.columns(
        [1.2, 0.95],
        gap="large"
    )

    # ---------- BÊN TRÁI: MENU ----------
    with left:
        st.subheader("🍽️ Thực đơn")

        if menu_df.empty:
            st.warning("Chưa có món ăn. Hãy thêm món trong mục Quản lý món ăn.")

        else:
            search = st.text_input(
                "Tìm món ăn",
                placeholder="Nhập tên món..."
            )

            categories = [
                "Tất cả"
            ] + sorted(
                menu_df["category"].dropna().unique().tolist()
            )

            selected_category = st.selectbox(
                "Danh mục món ăn",
                categories
            )

            filtered = menu_df.copy()

            if search:
                filtered = filtered[
                    filtered["name"].str.contains(
                        search,
                        case=False,
                        na=False
                    )
                ]

            if selected_category != "Tất cả":
                filtered = filtered[
                    filtered["category"] == selected_category
                ]

            if filtered.empty:
                st.info("Không tìm thấy món ăn phù hợp.")

            else:
                cards = st.columns(2)

                for idx, row in filtered.reset_index(drop=True).iterrows():

                    with cards[idx % 2]:

                        with st.container(border=True):

                            st.markdown(f"**{row['name']}**")
                            st.caption(row["category"])
                            st.markdown(f"### {money(row['price'])}")

                            item_id = int(row["id"])

                            qty = st.number_input(
                                "Số lượng",
                                min_value=1,
                                max_value=99,
                                value=1,
                                step=1,
                                key=f"menu_qty_{item_id}"
                            )

                            if st.button(
                                "＋ Thêm vào hóa đơn",
                                key=f"add_{item_id}",
                                use_container_width=True
                            ):

                                if item_id in st.session_state.cart:
                                    st.session_state.cart[item_id]["qty"] += int(qty)

                                else:
                                    st.session_state.cart[item_id] = {
                                        "id": item_id,
                                        "name": row["name"],
                                        "category": row["category"],
                                        "price": int(row["price"]),
                                        "qty": int(qty)
                                    }

                                st.toast(
                                    f"Đã thêm {row['name']} vào hóa đơn!"
                                )
                                st.rerun()

    # ---------- BÊN PHẢI: GIỎ HÀNG ----------
    with right:

        st.subheader("🛒 Hóa đơn hiện tại")

        customer_name = st.text_input(
            "Tên khách hàng (không bắt buộc)",
            key="customer_name",
            placeholder="Khách lẻ"
        )

        if not st.session_state.cart:
            st.info("Chưa có món nào trong hóa đơn.")

        else:

            remove_ids = []

            for item_id, item in list(
                st.session_state.cart.items()
            ):

                with st.container(border=True):

                    col_name, col_qty, col_remove = st.columns(
                        [2.2, 1, 0.5]
                    )

                    col_name.markdown(
                        f"**{item['name']}**"
                    )

                    col_name.caption(
                        f"{money(item['price'])}/phần"
                    )

                    new_qty = col_qty.number_input(
                        "SL",
                        min_value=1,
                        max_value=99,
                        value=int(item["qty"]),
                        key=f"cart_qty_{item_id}"
                    )

                    st.session_state.cart[item_id]["qty"] = int(new_qty)

                    if col_remove.button(
                        "🗑️",
                        key=f"remove_{item_id}"
                    ):
                        remove_ids.append(item_id)

                    st.caption(
                        "Thành tiền: "
                        f"**{money(item['price'] * new_qty)}**"
                    )

            for item_id in remove_ids:
                st.session_state.cart.pop(item_id, None)

            if remove_ids:
                st.rerun()

            # TÍNH TIỀN
            subtotal = sum(
                item["price"] * item["qty"]
                for item in st.session_state.cart.values()
            )

            st.divider()

            col_discount, col_vat = st.columns(2)

            with col_discount:
                discount_pct = st.number_input(
                    "Giảm giá (%)",
                    min_value=0,
                    max_value=100,
                    value=0,
                    step=1,
                    key="discount_input"
                )

            with col_vat:
                vat_pct = st.number_input(
                    "VAT (%)",
                    min_value=0.0,
                    max_value=100.0,
                    value=0.0,
                    step=1.0,
                    key="vat_input"
                )

            discount_amount = round(
                subtotal * discount_pct / 100
            )

            taxable_amount = max(
                0,
                subtotal - discount_amount
            )

            vat_amount = round(
                taxable_amount * vat_pct / 100
            )

            total = taxable_amount + vat_amount

            st.markdown(
                f"Tạm tính: **{money(subtotal)}**"
            )

            st.markdown(
                f"Giảm giá: **− {money(discount_amount)}**"
            )

            st.markdown(
                f"VAT ({vat_pct:g}%): **{money(vat_amount)}**"
            )

            st.markdown(
                f"## Tổng thanh toán: {money(total)}"
            )

            # PHƯƠNG THỨC THANH TOÁN
            payment_method = st.selectbox(
                "Phương thức thanh toán",
                ["Tiền mặt", "Chuyển khoản"],
                key="payment_method"
            )

            if payment_method == "Tiền mặt":

                cash_received = st.number_input(
                    "Tiền khách đưa (VNĐ)",
                    min_value=0,
                    max_value=1_000_000_000,
                    value=int(total),
                    step=1000,
                    key="cash_received"
                )

                change_amount = max(
                    0,
                    int(cash_received) - int(total)
                )

                if cash_received < total:
                    st.warning(
                        f"Khách còn thiếu {money(total - cash_received)}"
                    )

                else:
                    st.success(
                        f"Tiền thừa: {money(change_amount)}"
                    )

            else:
                cash_received = int(total)
                change_amount = 0

                st.info(
                    "Chuyển khoản được ghi nhận thủ công; "
                    "ứng dụng chưa kết nối ngân hàng."
                )

            # NÚT LƯU VÀ XÓA
            col_save, col_clear = st.columns(2)

            with col_save:

                if st.button(
                    "✅ Lưu hóa đơn",
                    type="primary",
                    use_container_width=True
                ):

                    if (
                        payment_method == "Tiền mặt"
                        and cash_received < total
                    ):
                        st.error(
                            "Số tiền khách đưa chưa đủ thanh toán."
                        )

                    else:

                        now = datetime.now().astimezone().isoformat(
                            timespec="seconds"
                        )

                        invoice_code = (
                            "BN-"
                            + datetime.now().strftime("%Y%m%d-%H%M%S")
                            + "-"
                            + uuid.uuid4().hex[:4].upper()
                        )

                        items = list(
                            st.session_state.cart.values()
                        )

                        with connect_db() as conn:

                            conn.execute("""
                                INSERT INTO orders (
                                    invoice_code,
                                    created_at,
                                    customer_name,
                                    payment_method,
                                    subtotal,
                                    discount_amount,
                                    vat_rate,
                                    vat_amount,
                                    total,
                                    cash_received,
                                    change_amount,
                                    items_json
                                )
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (
                                invoice_code,
                                now,
                                customer_name.strip(),
                                payment_method,
                                int(subtotal),
                                int(discount_amount),
                                float(vat_pct),
                                int(vat_amount),
                                int(total),
                                int(cash_received),
                                int(change_amount),
                                json.dumps(
                                    items,
                                    ensure_ascii=False
                                )
                            ))

                        st.session_state.last_invoice = {
                            "code": invoice_code,
                            "created_at": now,
                            "customer": customer_name.strip(),
                            "payment": payment_method,
                            "items": items,
                            "subtotal": subtotal,
                            "discount": discount_amount,
                            "vat_pct": vat_pct,
                            "vat": vat_amount,
                            "total": total,
                            "cash": cash_received,
                            "change": change_amount
                        }

                        st.session_state.cart = {}

                        st.success(
                            f"Đã lưu hóa đơn {invoice_code}!"
                        )

                        st.rerun()

            with col_clear:

                if st.button(
                    "🧹 Xóa giỏ hàng",
                    use_container_width=True
                ):

                    st.session_state.cart = {}
                    st.rerun()

    # ---------- HIỂN THỊ HÓA ĐƠN VỪA LƯU ----------
    if st.session_state.last_invoice:

        inv = st.session_state.last_invoice

        with st.expander(
            "🧾 Hóa đơn vừa lưu — xem / tải xuống",
            expanded=True
        ):

            lines = [
                "BẾP NHÀ - HÓA ĐƠN THANH TOÁN",
                f"Mã hóa đơn: {inv['code']}",
                f"Thời gian: {inv['created_at']}",
                f"Khách hàng: {inv['customer'] or 'Khách lẻ'}",
                "-" * 36
            ]

            for item in inv["items"]:
                lines.append(
                    f"{item['name']} x{item['qty']} | "
                    f"{money(item['price'] * item['qty'])}"
                )

            lines += [
                "-" * 36,
                f"Tạm tính: {money(inv['subtotal'])}",
                f"Giảm giá: -{money(inv['discount'])}",
                f"VAT ({inv['vat_pct']:g}%): {money(inv['vat'])}",
                f"TỔNG CỘNG: {money(inv['total'])}",
                f"Thanh toán: {inv['payment']}",
                f"Khách đưa: {money(inv['cash'])}",
                f"Tiền thừa: {money(inv['change'])}",
                "Cảm ơn quý khách!"
            ]

            receipt = "\n".join(lines)

            st.code(receipt, language=None)

            st.download_button(
                "⬇️ Tải hóa đơn (.txt)",
                data=receipt,
                file_name=f"{inv['code']}.txt",
                mime="text/plain"
            )


# ==================================================
# 7. QUẢN LÝ MÓN ĂN
# ==================================================

elif page == "🍽️ Quản lý món ăn":

    st.subheader("🍽️ Quản lý thực đơn")

    st.caption(
        "Thêm món mới hoặc chỉnh sửa thực đơn. "
        "Giá tiền tính bằng VNĐ."
    )

    with st.form("add_menu_item", clear_on_submit=True):

        st.markdown("**Thêm món ăn mới**")

        col1, col2, col3 = st.columns([2, 1.2, 1])

        name = col1.text_input(
            "Tên món",
            placeholder="Ví dụ: Bánh mì thịt"
        )

        category = col2.selectbox(
            "Danh mục",
            [
                "Món chính",
                "Món ăn vặt",
                "Đồ uống",
                "Tráng miệng",
                "Khác"
            ]
        )

        price = col3.number_input(
            "Giá bán (VNĐ)",
            min_value=0,
            max_value=100_000_000,
            value=20000,
            step=1000
        )

        submitted = st.form_submit_button(
            "＋ Thêm món",
            type="primary"
        )

        if submitted:

            if not name.strip():
                st.error("Vui lòng nhập tên món.")

            else:

                try:
                    with connect_db() as conn:
                        conn.execute("""
                            INSERT INTO menu (
                                name, category, price, active
                            )
                            VALUES (?, ?, ?, 1)
                        """, (
                            name.strip(),
                            category,
                            int(price)
                        ))

                    st.success(f"Đã thêm món {name.strip()}.")
                    st.rerun()

                except sqlite3.IntegrityError:
                    st.error(
                        "Tên món đã tồn tại. Hãy sử dụng tên khác."
                    )

    st.divider()
    st.markdown("**Danh sách món ăn**")

    all_menu = get_menu(active_only=False)

    if all_menu.empty:
        st.info("Chưa có món ăn nào.")

    else:

        edited = st.data_editor(
            all_menu[
                ["id", "name", "category", "price", "active"]
            ],
            use_container_width=True,
            hide_index=True,
            num_rows="fixed",
            disabled=["id"],
            column_config={
                "id": st.column_config.NumberColumn(
                    "ID",
                    format="%d"
                ),
                "name": st.column_config.TextColumn(
                    "Tên món",
                    required=True
                ),
                "category": st.column_config.SelectboxColumn(
                    "Danh mục",
                    options=[
                        "Món chính",
                        "Món ăn vặt",
                        "Đồ uống",
                        "Tráng miệng",
                        "Khác"
                    ],
                    required=True
                ),
                "price": st.column_config.NumberColumn(
                    "Giá (VNĐ)",
                    min_value=0,
                    step=1000,
                    format="%d"
                ),
                "active": st.column_config.CheckboxColumn(
                    "Đang bán?"
                )
            },
            key="menu_editor"
        )

        if st.button(
            "💾 Lưu thay đổi thực đơn",
            type="primary"
        ):

            try:
                with connect_db() as conn:

                    for _, row in edited.iterrows():

                        if not str(row["name"]).strip():
                            raise ValueError(
                                "Tên món không được để trống."
                            )

                        conn.execute("""
                            UPDATE menu
                            SET name = ?,
                                category = ?,
                                price = ?,
                                active = ?
                            WHERE id = ?
                        """, (
                            str(row["name"]).strip(),
                            str(row["category"]),
                            int(row["price"]),
                            int(bool(row["active"])),
                            int(row["id"])
                        ))

                st.success("Đã cập nhật thực đơn.")
                st.rerun()

            except (sqlite3.IntegrityError, ValueError) as error:
                st.error(f"Không thể lưu thay đổi: {error}")


# ==================================================
# 8. LỊCH SỬ VÀ THỐNG KÊ
# ==================================================

else:

    st.subheader("📊 Lịch sử & thống kê")

    orders_df = get_orders()

    if orders_df.empty:

        st.info(
            "Chưa có hóa đơn. "
            "Hãy tạo hóa đơn đầu tiên ở mục Tạo hóa đơn."
        )

    else:

        orders_df["created_at"] = pd.to_datetime(
            orders_df["created_at"],
            errors="coerce",
            utc=True
        ).dt.tz_convert("Asia/Ho_Chi_Minh")

        orders_df["ngay"] = orders_df["created_at"].dt.date

        today = date.today()
        today_orders = orders_df[
            orders_df["ngay"] == today
        ]

        col1, col2, col3 = st.columns(3)

        col1.metric(
            "Doanh thu hôm nay",
            money(today_orders["total"].sum())
        )

        col2.metric(
            "Hóa đơn hôm nay",
            str(len(today_orders))
        )

        col3.metric(
            "Tổng hóa đơn đã lưu",
            str(len(orders_df))
        )

        st.divider()
        st.markdown("**Lọc hóa đơn theo ngày**")

        col_start, col_end = st.columns(2)

        with col_start:
            start_date = st.date_input(
                "Từ ngày",
                value=min(orders_df["ngay"].min(), today)
            )

        with col_end:
            end_date = st.date_input(
                "Đến ngày",
                value=today
            )

        if start_date > end_date:

            st.error(
                "Ngày bắt đầu phải nhỏ hơn hoặc bằng ngày kết thúc."
            )

        else:

            filtered_orders = orders_df[
                (orders_df["ngay"] >= start_date)
                & (orders_df["ngay"] <= end_date)
            ].copy()

            st.metric(
                "Doanh thu trong khoảng đã chọn",
                money(filtered_orders["total"].sum())
            )

            display = filtered_orders[
                [
                    "invoice_code",
                    "created_at",
                    "customer_name",
                    "payment_method",
                    "subtotal",
                    "discount_amount",
                    "vat_amount",
                    "total"
                ]
            ].copy()

            display.columns = [
                "Mã hóa đơn",
                "Thời gian",
                "Khách hàng",
                "Thanh toán",
                "Tạm tính",
                "Giảm giá",
                "VAT",
                "Tổng tiền"
            ]

            for col in [
                "Tạm tính",
                "Giảm giá",
                "VAT",
                "Tổng tiền"
            ]:
                display[col] = display[col].map(money)

            st.dataframe(
                display,
                use_container_width=True,
                hide_index=True
            )

            # Xuất lịch sử ra CSV
            csv_data = filtered_orders.drop(
                columns=["items_json"],
                errors="ignore"
            ).to_csv(
                index=False
            ).encode("utf-8-sig")

            st.download_button(
                "⬇️ Xuất lịch sử CSV",
                data=csv_data,
                file_name="lich_su_hoa_don.csv",
                mime="text/csv"
            )

            # Xem chi tiết hóa đơn
            with st.expander("Xem chi tiết một hóa đơn"):

                choices = filtered_orders[
                    "invoice_code"
                ].tolist()

                if choices:

                    chosen = st.selectbox(
                        "Chọn mã hóa đơn",
                        choices
                    )

                    selected = filtered_orders[
                        filtered_orders["invoice_code"] == chosen
                    ].iloc[0]

                    st.write(
                        f"**Khách hàng:** "
                        f"{selected['customer_name'] or 'Khách lẻ'}"
                    )

                    st.write(
                        f"**Phương thức thanh toán:** "
                        f"{selected['payment_method']}"
                    )

                    try:
                        items = json.loads(
                            selected["items_json"]
                        )

                        detail_df = pd.DataFrame([
                            {
                                "Món ăn": item["name"],
                                "Số lượng": item["qty"],
                                "Đơn giá": money(item["price"]),
                                "Thành tiền": money(
                                    item["price"] * item["qty"]
                                )
                            }
                            for item in items
                        ])

                        st.dataframe(
                            detail_df,
                            use_container_width=True,
                            hide_index=True
                        )

                    except (ValueError, TypeError, KeyError):
                        st.warning(
                            "Không đọc được chi tiết hóa đơn."
                        )

        # Thống kê món bán chạy
        sold = {}

        for _, order in orders_df.iterrows():

            try:
                items = json.loads(order["items_json"])

                for item in items:
                    name = item["name"]

                    sold[name] = (
                        sold.get(name, 0) + int(item["qty"])
                    )

            except (ValueError, TypeError, KeyError):
                continue

        if sold:

            st.divider()
            st.markdown("**🏆 Top món bán chạy**")

            top_df = pd.DataFrame([
                {
                    "Món ăn": name,
                    "Số phần đã bán": quantity
                }
                for name, quantity in sold.items()
            ]).sort_values(
                "Số phần đã bán",
                ascending=False
            ).head(10)

            st.bar_chart(
                top_df.set_index("Món ăn")
            )


# =========================
# 9. CHÂN TRANG
# =========================

st.divider()

st.caption(
    "Bếp Nhà · Ứng dụng minh họa phục vụ bài tập Python và Streamlit."
)
