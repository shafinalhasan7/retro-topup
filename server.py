import os
import sqlite3
from typing import Optional, List
from fastapi import FastAPI, Request, Form, HTTPException, Depends, status, Response
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from database import get_db, get_setting, get_all_settings, set_setting, generate_order_code, hash_password
from auth import create_admin_token, verify_admin_token

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = FastAPI(title="Retro Topup", version="2.0.0")

# Static and Templates
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

def render(request: Request, name: str, context: Optional[dict] = None) -> HTMLResponse:
    ctx = dict(context) if context else {}
    ctx["request"] = request
    return templates.TemplateResponse(request=request, name=name, context=ctx)

# Inject site settings and active payment methods into every template context
def get_global_context():
    settings = get_all_settings()
    conn = get_db()
    payment_methods = conn.execute("SELECT * FROM payment_methods WHERE is_active = 1 ORDER BY sort_order ASC").fetchall()
    conn.close()
    return {
        "settings": settings,
        "payment_methods": [dict(pm) for pm in payment_methods]
    }

# Admin Dependency
def get_current_admin(request: Request) -> Optional[str]:
    token = request.cookies.get("admin_session")
    username = verify_admin_token(token)
    return username

def require_admin(request: Request) -> str:
    username = get_current_admin(request)
    if not username:
        raise HTTPException(
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            headers={"Location": "/admin/login"}
        )
    return username

# -------------------------------------------------------------
# PUBLIC ROUTES
# -------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    ctx = get_global_context()
    conn = get_db()
    
    # Games list
    games = conn.execute("SELECT * FROM games WHERE is_active = 1 ORDER BY sort_order ASC").fetchall()
    
    # Banners
    banners = conn.execute("SELECT * FROM banners WHERE is_active = 1 ORDER BY sort_order ASC").fetchall()
    
    # Categories
    categories = conn.execute("SELECT DISTINCT category FROM games WHERE is_active = 1").fetchall()
    category_list = [row['category'] for row in categories]
    
    # Recent completed orders ticker (for trust factor)
    recent_orders = conn.execute("""
        SELECT order_code, game_name, package_name, created_at 
        FROM orders 
        ORDER BY id DESC LIMIT 5
    """).fetchall()
    
    conn.close()

    return render(request, "index.html", {
        **ctx,
        "games": [dict(g) for g in games],
        "banners": [dict(b) for b in banners],
        "categories": category_list,
        "recent_orders": [dict(o) for o in recent_orders]
    })

@app.get("/game/{slug}", response_class=HTMLResponse)
def game_detail(request: Request, slug: str):
    ctx = get_global_context()
    conn = get_db()
    
    game = conn.execute("SELECT * FROM games WHERE slug = ? AND is_active = 1", (slug,)).fetchone()
    if not game:
        conn.close()
        raise HTTPException(status_code=404, detail="Game not found")
        
    packages = conn.execute("SELECT * FROM packages WHERE game_id = ? AND in_stock = 1 ORDER BY sort_order ASC, price ASC", (game['id'],)).fetchall()
    payment_methods = conn.execute("SELECT * FROM payment_methods WHERE is_active = 1 ORDER BY sort_order ASC").fetchall()
    
    conn.close()

    return render(request, "product.html", {
        **ctx,
        "game": dict(game),
        "packages": [dict(p) for p in packages],
        "payment_methods": [dict(pm) for pm in payment_methods]
    })

@app.post("/order/submit")
def submit_order(
    request: Request,
    game_id: int = Form(...),
    package_id: int = Form(...),
    player_info: str = Form(...),
    payment_method: str = Form(...),
    sender_number: str = Form(...),
    trx_id: str = Form(...),
    customer_whatsapp: str = Form(...)
):
    conn = get_db()
    game = conn.execute("SELECT * FROM games WHERE id = ?", (game_id,)).fetchone()
    package = conn.execute("SELECT * FROM packages WHERE id = ?", (package_id,)).fetchone()
    pm = conn.execute("SELECT * FROM payment_methods WHERE name = ?", (payment_method,)).fetchone()
    
    if not game or not package:
        conn.close()
        raise HTTPException(status_code=400, detail="Invalid game or package selected.")

    payment_num = pm['number'] if pm else "01925915240"
    order_code = generate_order_code()

    # Clean inputs
    player_info = player_info.strip()
    sender_number = sender_number.strip()
    trx_id = trx_id.strip().upper()
    customer_whatsapp = customer_whatsapp.strip()

    conn.execute("""
    INSERT INTO orders (
        order_code, game_id, game_name, package_id, package_name,
        amount, player_info, payment_method, payment_number,
        sender_number, trx_id, customer_whatsapp, status
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Pending')
    """, (
        order_code, game['id'], game['name'], package['id'], package['name'],
        package['price'], player_info, payment_method, payment_num,
        sender_number, trx_id, customer_whatsapp
    ))
    conn.commit()
    conn.close()

    return RedirectResponse(url=f"/order/{order_code}", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/order/{order_code}", response_class=HTMLResponse)
def order_success(request: Request, order_code: str):
    ctx = get_global_context()
    conn = get_db()
    order = conn.execute("SELECT * FROM orders WHERE order_code = ?", (order_code,)).fetchone()
    conn.close()

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    return render(request, "order_success.html", {
        **ctx,
        "order": dict(order)
    })

@app.get("/track", response_class=HTMLResponse)
def track_page(request: Request, q: Optional[str] = None):
    ctx = get_global_context()
    orders = []
    searched = False
    
    if q and q.strip():
        searched = True
        query_val = q.strip()
        conn = get_db()
        rows = conn.execute("""
        SELECT * FROM orders 
        WHERE order_code = ? OR sender_number = ? OR customer_whatsapp = ? OR trx_id = ?
        ORDER BY id DESC LIMIT 20
        """, (query_val, query_val, query_val, query_val)).fetchall()
        orders = [dict(r) for r in rows]
        conn.close()

    return render(request, "track.html", {
        **ctx,
        "orders": orders,
        "search_query": q or "",
        "searched": searched
    })

@app.get("/api/track/{query}")
def api_track_order(query: str):
    q = query.strip()
    conn = get_db()
    rows = conn.execute("""
    SELECT order_code, game_name, package_name, amount, player_info, 
           payment_method, status, admin_note, created_at 
    FROM orders 
    WHERE order_code = ? OR sender_number = ? OR customer_whatsapp = ? OR trx_id = ?
    ORDER BY id DESC LIMIT 10
    """, (q, q, q, q)).fetchall()
    conn.close()
    return {"orders": [dict(r) for r in rows]}

@app.get("/about", response_class=HTMLResponse)
def about_page(request: Request):
    ctx = get_global_context()
    return render(request, "about.html", ctx)

@app.get("/terms", response_class=HTMLResponse)
def terms_page(request: Request):
    ctx = get_global_context()
    return render(request, "terms.html", ctx)

# -------------------------------------------------------------
# ADMIN AUTHENTICATION
# -------------------------------------------------------------

@app.get("/admin/login", response_class=HTMLResponse)
def admin_login_page(request: Request, error: Optional[str] = None):
    if get_current_admin(request):
        return RedirectResponse(url="/admin", status_code=status.HTTP_302_FOUND)
        
    ctx = get_global_context()
    return render(request, "admin/login.html", {
        **ctx,
        "error": error
    })

@app.post("/admin/login")
def admin_login_submit(
    request: Request,
    response: Response,
    username: str = Form(...),
    password: str = Form(...)
):
    conn = get_db()
    admin = conn.execute("SELECT * FROM admins WHERE username = ?", (username.strip(),)).fetchone()
    conn.close()

    if not admin:
        return RedirectResponse(url="/admin/login?error=Invalid%20credentials", status_code=status.HTTP_303_SEE_OTHER)

    pwd_hash = hash_password(password)
    if admin['password_hash'] != pwd_hash:
        return RedirectResponse(url="/admin/login?error=Invalid%20username%20or%20password", status_code=status.HTTP_303_SEE_OTHER)

    token = create_admin_token(admin['username'])
    resp = RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)
    resp.set_cookie(
        key="admin_session",
        value=token,
        httponly=True,
        max_age=86400 * 7,
        samesite="lax"
    )
    return resp

@app.get("/admin/logout")
def admin_logout():
    resp = RedirectResponse(url="/admin/login", status_code=status.HTTP_303_SEE_OTHER)
    resp.delete_cookie("admin_session")
    return resp

# -------------------------------------------------------------
# ADMIN DASHBOARD & MANAGEMENT
# -------------------------------------------------------------

@app.get("/admin", response_class=HTMLResponse)
def admin_dashboard(request: Request, admin_user: str = Depends(require_admin)):
    ctx = get_global_context()
    conn = get_db()

    total_orders = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    total_revenue = conn.execute("SELECT COALESCE(SUM(amount), 0) FROM orders WHERE status = 'Completed'").fetchone()[0]
    pending_orders = conn.execute("SELECT COUNT(*) FROM orders WHERE status = 'Pending'").fetchone()[0]
    processing_orders = conn.execute("SELECT COUNT(*) FROM orders WHERE status = 'Processing'").fetchone()[0]
    completed_orders = conn.execute("SELECT COUNT(*) FROM orders WHERE status = 'Completed'").fetchone()[0]
    
    # Today's stats
    today_orders = conn.execute("SELECT COUNT(*) FROM orders WHERE date(created_at) = date('now')").fetchone()[0]
    today_revenue = conn.execute("SELECT COALESCE(SUM(amount), 0) FROM orders WHERE status = 'Completed' AND date(created_at) = date('now')").fetchone()[0]

    # Latest 10 orders
    recent_orders = conn.execute("""
        SELECT * FROM orders 
        ORDER BY id DESC LIMIT 10
    """).fetchall()

    conn.close()

    return render(request, "admin/dashboard.html", {
        **ctx,
        "admin_user": admin_user,
        "total_orders": total_orders,
        "total_revenue": total_revenue,
        "pending_orders": pending_orders,
        "processing_orders": processing_orders,
        "completed_orders": completed_orders,
        "today_orders": today_orders,
        "today_revenue": today_revenue,
        "recent_orders": [dict(o) for o in recent_orders]
    })

@app.get("/admin/orders", response_class=HTMLResponse)
def admin_orders_page(
    request: Request,
    status_filter: Optional[str] = None,
    q: Optional[str] = None,
    admin_user: str = Depends(require_admin)
):
    ctx = get_global_context()
    conn = get_db()

    query = "SELECT * FROM orders WHERE 1=1"
    params = []

    if status_filter and status_filter != "all":
        query += " AND status = ?"
        params.append(status_filter)

    if q and q.strip():
        term = f"%{q.strip()}%"
        query += " AND (order_code LIKE ? OR player_info LIKE ? OR trx_id LIKE ? OR sender_number LIKE ? OR customer_whatsapp LIKE ?)"
        params.extend([term, term, term, term, term])

    query += " ORDER BY id DESC LIMIT 100"

    orders = conn.execute(query, params).fetchall()
    conn.close()

    return render(request, "admin/orders.html", {
        **ctx,
        "admin_user": admin_user,
        "orders": [dict(o) for o in orders],
        "current_status": status_filter or "all",
        "search_query": q or ""
    })

@app.post("/admin/orders/{order_id}/update-status")
def admin_update_order_status(
    order_id: int,
    status: str = Form(...),
    admin_note: str = Form(""),
    admin_user: str = Depends(require_admin)
):
    conn = get_db()
    conn.execute("""
    UPDATE orders 
    SET status = ?, admin_note = ?, updated_at = CURRENT_TIMESTAMP
    WHERE id = ?
    """, (status, admin_note, order_id))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/admin/orders", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/admin/orders/{order_id}/delete")
def admin_delete_order(
    order_id: int,
    admin_user: str = Depends(require_admin)
):
    conn = get_db()
    conn.execute("DELETE FROM orders WHERE id = ?", (order_id,))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/admin/orders", status_code=status.HTTP_303_SEE_OTHER)

# -------------------------------------------------------------
# PRODUCTS & PACKAGES MANAGEMENT
# -------------------------------------------------------------

@app.get("/admin/products", response_class=HTMLResponse)
def admin_products_page(request: Request, admin_user: str = Depends(require_admin)):
    ctx = get_global_context()
    conn = get_db()
    
    games = conn.execute("""
        SELECT g.*, COUNT(p.id) as package_count 
        FROM games g 
        LEFT JOIN packages p ON g.id = p.game_id 
        GROUP BY g.id 
        ORDER BY g.sort_order ASC
    """).fetchall()
    
    conn.close()

    return render(request, "admin/products.html", {
        **ctx,
        "admin_user": admin_user,
        "games": [dict(g) for g in games]
    })

@app.post("/admin/products/add")
def admin_add_product(
    name: str = Form(...),
    slug: str = Form(...),
    category: str = Form("Games"),
    image_url: str = Form(...),
    badge: Optional[str] = Form(None),
    input_type: str = Form("uid"),
    input_label: str = Form("Player ID (UID)"),
    input_placeholder: str = Form("আপনার প্লেয়ার আইডি দিন"),
    delivery_time: str = Form("২ - ১০ মিনিট"),
    description: Optional[str] = Form(""),
    instructions: Optional[str] = Form(""),
    sort_order: int = Form(0),
    admin_user: str = Depends(require_admin)
):
    conn = get_db()
    slug_clean = slug.strip().lower().replace(" ", "-")
    conn.execute("""
    INSERT INTO games (name, slug, category, image_url, badge, input_type, input_label, input_placeholder, delivery_time, description, instructions, sort_order)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (name, slug_clean, category, image_url, badge, input_type, input_label, input_placeholder, delivery_time, description, instructions, sort_order))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/admin/products", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/admin/products/{game_id}/edit")
def admin_edit_product(
    game_id: int,
    name: str = Form(...),
    slug: str = Form(...),
    category: str = Form(...),
    image_url: str = Form(...),
    badge: Optional[str] = Form(None),
    input_type: str = Form(...),
    input_label: str = Form(...),
    input_placeholder: str = Form(...),
    delivery_time: str = Form(...),
    description: Optional[str] = Form(""),
    instructions: Optional[str] = Form(""),
    is_active: int = Form(1),
    sort_order: int = Form(0),
    admin_user: str = Depends(require_admin)
):
    conn = get_db()
    slug_clean = slug.strip().lower().replace(" ", "-")
    conn.execute("""
    UPDATE games 
    SET name=?, slug=?, category=?, image_url=?, badge=?, input_type=?, input_label=?, input_placeholder=?, delivery_time=?, description=?, instructions=?, is_active=?, sort_order=?
    WHERE id=?
    """, (name, slug_clean, category, image_url, badge, input_type, input_label, input_placeholder, delivery_time, description, instructions, is_active, sort_order, game_id))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/admin/products", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/admin/products/{game_id}/delete")
def admin_delete_product(
    game_id: int,
    admin_user: str = Depends(require_admin)
):
    conn = get_db()
    conn.execute("DELETE FROM games WHERE id = ?", (game_id,))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/admin/products", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/admin/products/{game_id}/packages", response_class=HTMLResponse)
def admin_packages_page(
    request: Request,
    game_id: int,
    admin_user: str = Depends(require_admin)
):
    ctx = get_global_context()
    conn = get_db()
    game = conn.execute("SELECT * FROM games WHERE id = ?", (game_id,)).fetchone()
    if not game:
        conn.close()
        raise HTTPException(status_code=404, detail="Game not found")
        
    packages = conn.execute("SELECT * FROM packages WHERE game_id = ? ORDER BY sort_order ASC, price ASC", (game_id,)).fetchall()
    conn.close()

    return render(request, "admin/packages.html", {
        **ctx,
        "admin_user": admin_user,
        "game": dict(game),
        "packages": [dict(p) for p in packages]
    })

@app.post("/admin/packages/add")
def admin_add_package(
    game_id: int = Form(...),
    name: str = Form(...),
    category: str = Form("standard"),
    price: float = Form(...),
    original_price: Optional[float] = Form(None),
    badge: Optional[str] = Form(None),
    sort_order: int = Form(0),
    admin_user: str = Depends(require_admin)
):
    conn = get_db()
    conn.execute("""
    INSERT INTO packages (game_id, name, category, price, original_price, badge, in_stock, sort_order)
    VALUES (?, ?, ?, ?, ?, ?, 1, ?)
    """, (game_id, name, category, price, original_price, badge, sort_order))
    conn.commit()
    conn.close()
    return RedirectResponse(url=f"/admin/products/{game_id}/packages", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/admin/packages/{package_id}/edit")
def admin_edit_package(
    package_id: int,
    game_id: int = Form(...),
    name: str = Form(...),
    price: float = Form(...),
    original_price: Optional[float] = Form(None),
    badge: Optional[str] = Form(None),
    in_stock: int = Form(1),
    sort_order: int = Form(0),
    admin_user: str = Depends(require_admin)
):
    conn = get_db()
    conn.execute("""
    UPDATE packages 
    SET name=?, price=?, original_price=?, badge=?, in_stock=?, sort_order=?
    WHERE id=?
    """, (name, price, original_price, badge, in_stock, sort_order, package_id))
    conn.commit()
    conn.close()
    return RedirectResponse(url=f"/admin/products/{game_id}/packages", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/admin/packages/{package_id}/delete")
def admin_delete_package(
    package_id: int,
    game_id: int = Form(...),
    admin_user: str = Depends(require_admin)
):
    conn = get_db()
    conn.execute("DELETE FROM packages WHERE id = ?", (package_id,))
    conn.commit()
    conn.close()
    return RedirectResponse(url=f"/admin/products/{game_id}/packages", status_code=status.HTTP_303_SEE_OTHER)

# -------------------------------------------------------------
# PAYMENT METHODS MANAGEMENT
# -------------------------------------------------------------

@app.get("/admin/payments", response_class=HTMLResponse)
def admin_payments_page(request: Request, admin_user: str = Depends(require_admin)):
    ctx = get_global_context()
    conn = get_db()
    methods = conn.execute("SELECT * FROM payment_methods ORDER BY sort_order ASC").fetchall()
    conn.close()

    return render(request, "admin/payments.html", {
        **ctx,
        "admin_user": admin_user,
        "methods": [dict(m) for m in methods]
    })

@app.post("/admin/payments/{pm_id}/edit")
def admin_edit_payment_method(
    pm_id: int,
    name: str = Form(...),
    type: str = Form(...),
    number: str = Form(...),
    instructions: str = Form(...),
    logo_color: str = Form(...),
    is_active: int = Form(1),
    admin_user: str = Depends(require_admin)
):
    conn = get_db()
    conn.execute("""
    UPDATE payment_methods 
    SET name=?, type=?, number=?, instructions=?, logo_color=?, is_active=?
    WHERE id=?
    """, (name, type, number.strip(), instructions, logo_color, is_active, pm_id))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/admin/payments", status_code=status.HTTP_303_SEE_OTHER)

# -------------------------------------------------------------
# SETTINGS & CUSTOMIZATION
# -------------------------------------------------------------

@app.get("/admin/settings", response_class=HTMLResponse)
def admin_settings_page(
    request: Request,
    msg: Optional[str] = None,
    admin_user: str = Depends(require_admin)
):
    ctx = get_global_context()
    return render(request, "admin/settings.html", {
        **ctx,
        "admin_user": admin_user,
        "msg": msg
    })

@app.post("/admin/settings/update")
def admin_update_settings(
    site_name: str = Form(...),
    tagline: str = Form(...),
    site_notice: str = Form(...),
    whatsapp_number: str = Form(...),
    support_phone: str = Form(...),
    hero_title: str = Form(...),
    hero_subtitle: str = Form(...),
    delivery_time: str = Form(...),
    working_hours: str = Form(...),
    contact_email: str = Form(...),
    facebook_page: Optional[str] = Form(""),
    telegram_group: Optional[str] = Form(""),
    admin_user: str = Depends(require_admin)
):
    set_setting("site_name", site_name.strip())
    set_setting("tagline", tagline.strip())
    set_setting("site_notice", site_notice.strip())
    set_setting("whatsapp_number", whatsapp_number.strip())
    set_setting("support_phone", support_phone.strip())
    set_setting("hero_title", hero_title.strip())
    set_setting("hero_subtitle", hero_subtitle.strip())
    set_setting("delivery_time", delivery_time.strip())
    set_setting("working_hours", working_hours.strip())
    set_setting("contact_email", contact_email.strip())
    set_setting("facebook_page", (facebook_page or "").strip())
    set_setting("telegram_group", (telegram_group or "").strip())

    return RedirectResponse(url="/admin/settings?msg=Settings%20updated%20successfully!", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/admin/change-password")
def admin_change_password(
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    admin_user: str = Depends(require_admin)
):
    if new_password != confirm_password:
        return RedirectResponse(url="/admin/settings?msg=New%20passwords%20do%20not%20match!#security", status_code=status.HTTP_303_SEE_OTHER)

    conn = get_db()
    admin = conn.execute("SELECT * FROM admins WHERE username = ?", (admin_user,)).fetchone()
    if not admin or admin['password_hash'] != hash_password(current_password):
        conn.close()
        return RedirectResponse(url="/admin/settings?msg=Current%20password%20is%20incorrect!#security", status_code=status.HTTP_303_SEE_OTHER)

    new_hash = hash_password(new_password)
    conn.execute("UPDATE admins SET password_hash = ? WHERE username = ?", (new_hash, admin_user))
    conn.commit()
    conn.close()

    return RedirectResponse(url="/admin/settings?msg=Password%20successfully%20changed!#security", status_code=status.HTTP_303_SEE_OTHER)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
