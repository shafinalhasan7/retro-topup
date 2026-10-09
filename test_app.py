from fastapi.testclient import TestClient
from server import app
from database import init_db

init_db()
client = TestClient(app)

def test_home():
    res = client.get("/")
    assert res.status_code == 200
    assert "Retro Topup" in res.text
    assert "01925915240" in res.text
    print("Test home OK!")

def test_game_page():
    res = client.get("/game/free-fire-bd")
    assert res.status_code == 200
    assert "Free Fire" in res.text
    assert "01925915240" in res.text
    print("Test game page OK!")

def test_order_submission():
    data = {
        "game_id": 1,
        "package_id": 1,
        "player_info": "1928374650",
        "payment_method": "bKash",
        "sender_number": "01711223344",
        "trx_id": "TX98234B",
        "customer_whatsapp": "01925915240"
    }
    res = client.post("/order/submit", data=data, follow_redirects=False)
    assert res.status_code in [302, 303]
    redirect_url = res.headers["location"]
    assert "/order/RT-" in redirect_url
    print(f"Test order submit OK! Redirected to {redirect_url}")

    # Check order page
    res2 = client.get(redirect_url)
    assert res2.status_code == 200
    assert "TX98234B" in res2.text
    print("Test order receipt OK!")

def test_admin_flow():
    # Login page
    res = client.get("/admin/login")
    assert res.status_code == 200
    assert "admin" in res.text

    # Login submit
    res = client.post("/admin/login", data={"username": "admin", "password": "wrongpassword"}, follow_redirects=False)
    assert res.status_code in [302, 303]
    assert "error=" in res.headers["location"]

    # Login correct
    res = client.post("/admin/login", data={"username": "admin", "password": "admin123"}, follow_redirects=False)
    assert res.status_code in [302, 303]
    assert "admin_session" in res.cookies

    session_cookie = res.cookies["admin_session"]

    # Admin dashboard
    client.cookies.set("admin_session", session_cookie)
    res_dash = client.get("/admin")
    assert res_dash.status_code == 200
    assert "অ্যাডমিন ওভারভিউ" in res_dash.text
    print("Test admin dashboard OK!")

    # Admin orders
    res_orders = client.get("/admin/orders")
    assert res_orders.status_code == 200
    assert "অর্ডার ব্যবস্থাপনা" in res_orders.text
    print("Test admin orders OK!")

    # Admin products
    res_products = client.get("/admin/products")
    assert res_products.status_code == 200
    assert "গেম ও প্রোডাক্ট ব্যবস্থাপনা" in res_products.text
    print("Test admin products OK!")

    # Admin payments
    res_payments = client.get("/admin/payments")
    assert res_payments.status_code == 200
    assert "01925915240" in res_payments.text
    print("Test admin payments OK!")

    # Admin settings
    res_settings = client.get("/admin/settings")
    assert res_settings.status_code == 200
    assert "01925915240" in res_settings.text
    print("Test admin settings OK!")

if __name__ == "__main__":
    test_home()
    test_game_page()
    test_order_submission()
    test_admin_flow()
    print("\nALL RETRO TOPUP SYSTEM TESTS PASSED SUCCESSFULLY!")
